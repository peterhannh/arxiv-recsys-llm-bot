"""Fetch recent RecSys & LLM papers from Semantic Scholar."""

import time
from datetime import datetime

import requests

from arxiv_recsys_llm_bot.config import S2_API_KEY, S2_SEARCH_QUERIES, log

# Seconds between queries (S2 allows 1 RPS with key; add safety margin).
QUERY_DELAY = 3.0
S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_FIELDS = "title,abstract,authors,externalIds,publicationDate,url,venue,openAccessPdf"
MAX_RESULTS_PER_QUERY = 100


def fetch_semantic_scholar_papers(cutoff: datetime) -> list[dict]:
    """Fetch recent RecSys & LLM papers from Semantic Scholar since *cutoff*."""
    headers = {}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY

    cutoff_str = cutoff.strftime("%Y-%m-%d")
    seen_ids: set[str] = set()
    papers: list[dict] = []

    for qi, query in enumerate(S2_SEARCH_QUERIES):
        log.info("S2 query %d/%d: %s", qi + 1, len(S2_SEARCH_QUERIES), query)

        try:
            resp = requests.get(
                S2_SEARCH_URL,
                params={
                    "query": query,
                    "limit": MAX_RESULTS_PER_QUERY,
                    "fields": S2_FIELDS,
                    "publicationDateOrYear": f"{cutoff_str}:",
                    "fieldsOfStudy": "Computer Science",
                },
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            log.warning("S2 query %d/%d failed (%s), skipping: %s",
                        qi + 1, len(S2_SEARCH_QUERIES), e, query)
            if qi < len(S2_SEARCH_QUERIES) - 1:
                time.sleep(QUERY_DELAY)
            continue

        for item in data.get("data") or []:
            s2_id = item.get("paperId", "")
            if not s2_id or s2_id in seen_ids:
                continue
            seen_ids.add(s2_id)

            title = (item.get("title") or "").replace("\n", " ").strip()
            abstract = (item.get("abstract") or "").replace("\n", " ").strip()
            if not title:
                continue

            # Extract external IDs
            ext_ids = item.get("externalIds") or {}
            arxiv_id = ext_ids.get("ArXiv", "")
            doi = ext_ids.get("DOI", "")

            # Build URL: prefer ArXiv link, fall back to S2
            if arxiv_id:
                url = f"https://arxiv.org/abs/{arxiv_id}"
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
            else:
                url = item.get("url") or f"https://www.semanticscholar.org/paper/{s2_id}"
                oap = item.get("openAccessPdf") or {}
                pdf_url = oap.get("url", url)

            authors = [a.get("name", "") for a in (item.get("authors") or [])]

            papers.append({
                "id": arxiv_id if arxiv_id else f"s2:{s2_id}",
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "categories": [],
                "published": item.get("publicationDate") or "",
                "url": url,
                "pdf_url": pdf_url,
                "comment": item.get("venue") or "",
                "doi": doi,
                "source": "s2",
            })

        if qi < len(S2_SEARCH_QUERIES) - 1:
            log.info("Waiting %.0fs before next S2 query...", QUERY_DELAY)
            time.sleep(QUERY_DELAY)

    log.info("S2: fetched %d unique papers since %s", len(papers), cutoff_str)
    return papers


# ---------------------------------------------------------------------------
# Batch affiliation enrichment (called after dedup, before classification)
# ---------------------------------------------------------------------------
S2_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
S2_BATCH_FIELDS = "authors,authors.affiliations"
S2_BATCH_SIZE = 100  # S2 allows up to 500, but 100 is safer


def enrich_papers_with_affiliations(papers: list[dict]) -> None:
    """Batch-fetch author affiliations from Semantic Scholar and attach to papers."""
    headers = {"Content-Type": "application/json"}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY

    # Build S2 lookup IDs: prefer ArXiv ID, fall back to S2 paper ID
    lookup_ids: list[str] = []
    paper_index_map: list[int] = []  # parallel to lookup_ids
    for i, p in enumerate(papers):
        pid = p.get("id", "")
        if pid.startswith("s2:"):
            lookup_ids.append(pid[3:])  # raw S2 paper ID
        elif pid:
            lookup_ids.append(f"ARXIV:{pid}")
        else:
            continue
        paper_index_map.append(i)

    if not lookup_ids:
        return

    enriched = 0
    for batch_start in range(0, len(lookup_ids), S2_BATCH_SIZE):
        batch_ids = lookup_ids[batch_start : batch_start + S2_BATCH_SIZE]
        batch_indices = paper_index_map[batch_start : batch_start + S2_BATCH_SIZE]

        try:
            resp = requests.post(
                S2_BATCH_URL,
                params={"fields": S2_BATCH_FIELDS},
                json={"ids": batch_ids},
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            results = resp.json()
        except requests.RequestException as e:
            log.warning("S2 batch affiliation lookup failed: %s", e)
            continue

        for item, paper_idx in zip(results, batch_indices):
            if item is None:
                continue
            affiliations = set()
            for author in item.get("authors") or []:
                for aff in author.get("affiliations") or []:
                    aff = aff.strip()
                    if aff:
                        affiliations.add(aff)
            if affiliations:
                papers[paper_idx]["affiliations"] = sorted(affiliations)
                enriched += 1

        if batch_start + S2_BATCH_SIZE < len(lookup_ids):
            time.sleep(QUERY_DELAY)

    log.info("S2 enrichment: added affiliations to %d / %d papers", enriched, len(papers))
