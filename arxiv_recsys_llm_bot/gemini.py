"""Gemini-based paper classification and summary generation."""

import json
import time

from google import genai
from google.genai import types

from arxiv_recsys_llm_bot.config import BATCH_SIZE, GEMINI_MODEL, MAX_GEMINI_CALLS, log

# ---------------------------------------------------------------------------
# Classification prompt
# ---------------------------------------------------------------------------
CLASSIFICATION_SYSTEM_PROMPT = """\
You are an expert at classifying whether academic papers come from industry or academia.

Given a batch of papers with their metadata, classify each one.

## Classification rules (in priority order):

1. **Recognize industry authors**: Use your knowledge of well-known researchers and \
their current affiliations. Many authors at major tech companies publish actively in \
recommendation systems, information retrieval, NLP, and LLM research.

2. **Check paper content for industry signals**:
   - Author email domains or affiliations mentioned in the abstract or comments
   - Mentions of company names, products, or platforms
   - Phrases like "deployed at", "A/B test", "serving N million users", "production"
   - Results on proprietary/internal datasets or live traffic experiments

3. **Common industry companies** (non-exhaustive): Google, DeepMind, Meta, FAIR, \
Amazon, AWS, Microsoft, MSR, Apple, Netflix, Spotify, Alibaba, Ant Group, Tencent, \
ByteDance, TikTok, Douyin, Huawei, JD.com, Baidu, LinkedIn, Pinterest, Uber, \
Airbnb, eBay, Yahoo, Snap, Twitter/X, NVIDIA, Samsung, Adobe, Salesforce, \
Kuaishou, Meituan, Shopee, Grab, Yandex, Criteo, Booking, PayPal, Bloomberg, \
IBM Research, Walmart, Instacart, DoorDash, Lyft, Roku, Etsy, Cohere, \
OpenAI, Anthropic, Mistral, AI21 Labs, Character.AI, etc.

4. **Default to "academia"** when there are no industry signals at all.

5. **Use "unknown" only as a last resort** — this should be very rare.

## Output format:
Respond with ONLY a JSON array. Each element:
  {"paper_index": <int>, "classification": "industry"|"academia"|"unknown", \
"company": "<specific company name(s) separated by commas if industry, empty string otherwise>", \
"reason": "<brief reason for classification>"}
"""


def classify_papers_with_gemini(
    papers: list[dict],
    gemini_client: genai.Client,
    call_counter: dict,
    max_calls: int = MAX_GEMINI_CALLS,
) -> list[dict]:
    """Classify papers in batches using Gemini. Modifies papers in-place."""
    total = len(papers)
    if total == 0:
        return papers

    for batch_start in range(0, total, BATCH_SIZE):
        if call_counter["count"] >= max_calls:
            log.warning(
                "Reached Gemini call limit (%d). Remaining papers left unclassified.",
                max_calls,
            )
            break

        batch = papers[batch_start : batch_start + BATCH_SIZE]
        prompt_parts = []
        for i, p in enumerate(batch):
            authors_str = ", ".join(p["authors"][:15])
            abstract_snippet = p["abstract"][:400]

            prompt_parts.append(
                f"Paper {i}:\n"
                f"  Title: {p['title']}\n"
                f"  Authors: {authors_str}\n"
                f"  Abstract: {abstract_snippet}\n"
                f"  Comment: {p.get('comment', '')}\n"
            )

        prompt = (
            "Classify each paper below as industry or academia.\n\n"
            + "\n".join(prompt_parts)
        )

        log.info(
            "Gemini call %d: classifying papers %d-%d of %d",
            call_counter["count"] + 1,
            batch_start,
            batch_start + len(batch) - 1,
            total,
        )

        response = None
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=CLASSIFICATION_SYSTEM_PROMPT,
                    temperature=0.0,
                    max_output_tokens=4096,
                    response_mime_type="application/json",
                ),
            )
            call_counter["count"] += 1

            raw_text = (response.text or "").strip()
            if not raw_text:
                log.error("Gemini returned empty response (possibly safety-filtered)")
                continue

            classifications = json.loads(raw_text)
            if not isinstance(classifications, list):
                log.error("Expected JSON array from Gemini, got %s", type(classifications).__name__)
                continue

            for item in classifications:
                idx = item.get("paper_index", -1)
                if 0 <= idx < len(batch):
                    batch[idx]["classification"] = item.get("classification", "unknown")
                    batch[idx]["company"] = item.get("company", "")
                    batch[idx]["classification_reason"] = item.get("reason", "")

        except json.JSONDecodeError as e:
            log.error("Failed to parse Gemini response as JSON: %s", e)
            raw = (getattr(response, "text", None) or "N/A")[:500]
            log.error("Raw response: %s", raw)
        except Exception as e:
            log.error("Gemini API error: %s", e)
            call_counter["count"] += 1  # Count attempted calls

        time.sleep(1)

    # Mark any unclassified papers
    for p in papers:
        if "classification" not in p:
            p["classification"] = "unknown"
            p["company"] = ""
            p["classification_reason"] = ""

    return papers


def generate_summaries(
    industry_papers: list[dict],
    gemini_client: genai.Client,
    call_counter: dict,
    max_calls: int = MAX_GEMINI_CALLS,
) -> None:
    """Use Gemini to generate a concise summary of each industry paper."""
    if not industry_papers or call_counter["count"] >= max_calls:
        return

    cap = 30
    if len(industry_papers) > cap:
        log.info(
            "Limiting summary generation to first %d of %d industry papers",
            cap, len(industry_papers),
        )

    papers_text = []
    for i, p in enumerate(industry_papers[:cap]):
        papers_text.append(
            f"Paper {i}:\n"
            f"  Title: {p['title']}\n"
            f"  Authors: {', '.join(p['authors'][:10])}\n"
            f"  Company: {p.get('company', 'N/A')}\n"
            f"  Abstract: {p['abstract'][:500]}\n"
        )

    prompt = (
        "For each paper below, write a 2-3 sentence summary highlighting "
        "the key contribution and why it matters for recommendation systems, "
        "information retrieval, or LLM research. "
        "Focus on practical implications.\n\n"
        + "\n".join(papers_text)
        + '\n\nReturn a JSON array: [{"paper_index": <int>, "summary": "..."}]'
    )

    response = None
    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=8192,
                response_mime_type="application/json",
            ),
        )
        call_counter["count"] += 1

        raw_text = (response.text or "").strip()
        if not raw_text:
            log.error("Gemini returned empty summary response")
            return

        summaries = json.loads(raw_text)
        if not isinstance(summaries, list):
            log.error("Expected JSON array for summaries, got %s", type(summaries).__name__)
            return

        for item in summaries:
            raw_idx = item.get("paper_index")
            if raw_idx is None:
                continue
            idx = int(raw_idx)
            if 0 <= idx < len(industry_papers):
                industry_papers[idx]["summary"] = item.get("summary", "")

    except Exception as e:
        log.error("Summary generation failed: %s", e)
        call_counter["count"] += 1  # Count attempted calls
