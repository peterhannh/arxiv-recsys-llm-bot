"""Fetch trending papers from HuggingFace Daily Papers."""

import requests

from arxiv_recsys_llm_bot.config import HF_RELEVANCE_KEYWORDS, log

HF_DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"


def _is_relevant(title: str, abstract: str) -> bool:
    """Check if a paper matches RecSys/LLM/IR keywords."""
    text = f"{title} {abstract}".lower()
    return any(kw in text for kw in HF_RELEVANCE_KEYWORDS)


def fetch_huggingface_papers() -> list[dict]:
    """Fetch today's HuggingFace Daily Papers, filtered for relevance."""
    try:
        resp = requests.get(HF_DAILY_PAPERS_URL, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        log.warning("HuggingFace Daily Papers fetch failed: %s", e)
        return []

    papers: list[dict] = []
    seen_ids: set[str] = set()

    for entry in data:
        paper = entry.get("paper") or {}
        arxiv_id = paper.get("id", "")
        if not arxiv_id or arxiv_id in seen_ids:
            continue
        seen_ids.add(arxiv_id)

        title = (paper.get("title") or "").replace("\n", " ").strip()
        abstract = (paper.get("summary") or "").replace("\n", " ").strip()

        if not title or not _is_relevant(title, abstract):
            continue

        authors = [a.get("name", "") for a in (paper.get("authors") or [])]
        upvotes = entry.get("paper", {}).get("upvotes", 0)
        if upvotes == 0:
            upvotes = entry.get("numUpvotes", 0)

        papers.append({
            "id": arxiv_id,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "categories": [],
            "published": paper.get("publishedAt", "")[:10],
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "comment": "",
            "hf_upvotes": upvotes,
            "source": "hf",
        })

    log.info("HuggingFace: fetched %d relevant papers", len(papers))
    return papers
