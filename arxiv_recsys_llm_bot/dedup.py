"""Three-layer deduplication for papers from multiple sources."""

import re

from arxiv_recsys_llm_bot.config import log


def normalize_arxiv_id(raw: str) -> str:
    """Normalize an ArXiv ID: strip URL prefix and version suffix."""
    if not raw:
        return ""
    # Strip URL prefixes like https://arxiv.org/abs/
    raw = re.sub(r"^https?://arxiv\.org/(abs|pdf)/", "", raw)
    # Strip version suffix (e.g., v1, v2)
    raw = re.sub(r"v\d+$", "", raw)
    return raw.strip()


def normalize_doi(raw: str) -> str:
    """Normalize a DOI: lowercase, strip URL prefix."""
    if not raw:
        return ""
    raw = re.sub(r"^https?://(dx\.)?doi\.org/", "", raw)
    return raw.strip().lower()


def normalize_title(title: str) -> str:
    """Normalize a title for fuzzy matching: lowercase, strip non-alphanumeric."""
    if not title:
        return ""
    # Remove common LaTeX commands
    title = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", title)
    title = re.sub(r"[{}\$\\]", "", title)
    # Lowercase, keep only alphanumeric and spaces
    title = re.sub(r"[^a-z0-9 ]", "", title.lower())
    # Collapse whitespace
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _merge_paper(existing: dict, new: dict) -> None:
    """Merge metadata from *new* into *existing* (in-place)."""
    # Keep longer abstract
    if len(new.get("abstract", "")) > len(existing.get("abstract", "")):
        existing["abstract"] = new["abstract"]

    # Union sources
    ex_sources = set(existing.get("source", "").split(","))
    new_sources = set(new.get("source", "").split(","))
    existing["source"] = ",".join(sorted(ex_sources | new_sources - {""}))

    # Carry over HF upvotes
    if new.get("hf_upvotes", 0) > existing.get("hf_upvotes", 0):
        existing["hf_upvotes"] = new["hf_upvotes"]

    # Carry over DOI if missing
    if new.get("doi") and not existing.get("doi"):
        existing["doi"] = new["doi"]

    # Carry over categories if empty
    if new.get("categories") and not existing.get("categories"):
        existing["categories"] = new["categories"]


def deduplicate_papers(papers: list[dict]) -> list[dict]:
    """Deduplicate papers using ArXiv ID, DOI, and normalized title.

    Papers should be ordered by source priority (ArXiv first, then S2, then HF).
    The first occurrence is kept as the primary record; later duplicates are merged in.
    """
    seen_arxiv: dict[str, int] = {}   # normalized arxiv_id -> index in result
    seen_doi: dict[str, int] = {}     # normalized doi -> index in result
    seen_title: dict[str, int] = {}   # normalized title -> index in result
    result: list[dict] = []

    for paper in papers:
        # Layer 1: ArXiv ID
        arxiv_id = normalize_arxiv_id(paper.get("id", ""))
        if arxiv_id and not arxiv_id.startswith("s2:"):
            if arxiv_id in seen_arxiv:
                _merge_paper(result[seen_arxiv[arxiv_id]], paper)
                continue

        # Layer 2: DOI
        doi = normalize_doi(paper.get("doi", ""))
        if doi:
            if doi in seen_doi:
                _merge_paper(result[seen_doi[doi]], paper)
                continue

        # Layer 3: Normalized title (skip very short titles to avoid false positives)
        norm_title = normalize_title(paper.get("title", ""))
        if len(norm_title) >= 30:
            if norm_title in seen_title:
                _merge_paper(result[seen_title[norm_title]], paper)
                continue

        # Not a duplicate — add to result
        idx = len(result)
        result.append(paper)

        if arxiv_id and not arxiv_id.startswith("s2:"):
            seen_arxiv[arxiv_id] = idx
        if doi:
            seen_doi[doi] = idx
        if len(norm_title) >= 30:
            seen_title[norm_title] = idx

    deduped = len(papers) - len(result)
    log.info("Dedup: %d papers in, %d unique out (%d duplicates removed)",
             len(papers), len(result), deduped)
    return result
