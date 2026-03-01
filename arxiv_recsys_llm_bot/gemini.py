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
You are an expert at classifying academic papers. Given a batch of papers, perform \
TWO checks for each paper:

## Step A — Relevance gate

Is this paper about ONE of the following topics?
1. **Recommendation systems** (collaborative filtering, CTR prediction, session-based \
recommendations, sequential recommendation, conversational recommendation, etc.)
2. **RecSys × LLM** (using large language models for recommendations, LLM-based ranking \
or scoring in recommender systems, prompt-based recommendations, etc.)
3. **LLM research with direct applications to ranking/retrieval for recommendations** \
(learning to rank, re-ranking with LLMs, generative retrieval for recommendations, etc.)

If the paper is NOT about any of these topics, mark it as `"relevant": false`. \
Papers about generic NLP, computer vision, speech, pure information extraction, \
general RAG without a recommendation angle, or other unrelated topics are NOT relevant.

## Step B — Industry affiliation (only for relevant papers)

Does **at least one author** have an affiliation with an industry company? \
Classify based on AUTHOR AFFILIATIONS, not paper content.

**How to determine author affiliation:**
- Check author names against your knowledge of well-known researchers at major \
companies — many industry researchers in RecSys, IR, and LLM publish actively
- Look for affiliation info in the comments field (e.g. "Work done at Google")
- Look for company email domains or explicit affiliations in abstract/comments
- Do NOT classify as "industry" based solely on content signals like "A/B test", \
"production system", or "deployed" — the author must actually be with a company

**Common industry companies** (non-exhaustive): Google, DeepMind, Meta, FAIR, \
Amazon, AWS, Microsoft, MSR, Apple, Netflix, Spotify, Alibaba, Ant Group, Tencent, \
ByteDance, TikTok, Douyin, Huawei, JD.com, Baidu, LinkedIn, Pinterest, Uber, \
Airbnb, eBay, Yahoo, Snap, Twitter/X, NVIDIA, Samsung, Adobe, Salesforce, \
Kuaishou, Meituan, Shopee, Grab, Yandex, Criteo, Booking, PayPal, Bloomberg, \
IBM Research, Walmart, Instacart, DoorDash, Lyft, Roku, Etsy, Cohere, \
OpenAI, Anthropic, Mistral, AI21 Labs, Character.AI, etc.

## Output format:
Respond with ONLY a JSON array. Each element:
  {"paper_index": <int>, "relevant": true|false, \
"classification": "industry"|"academia"|"unknown", \
"company": "<specific company name(s) if industry, empty string otherwise>", \
"reason": "<brief reason for relevance and classification decisions>"}

For irrelevant papers, set classification to "irrelevant" and company to "".
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
                    relevant = item.get("relevant", True)
                    if not relevant:
                        batch[idx]["classification"] = "irrelevant"
                        batch[idx]["company"] = ""
                    else:
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
