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
