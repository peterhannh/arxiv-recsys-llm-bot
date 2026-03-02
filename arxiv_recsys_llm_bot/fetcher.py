"""Fetch recent RecSys & LLM papers from ArXiv."""

import re
import time
from datetime import datetime, timezone

import arxiv

from arxiv_recsys_llm_bot.config import SEARCH_QUERIES, log

# Seconds to wait between queries to avoid ArXiv 429 rate limits.
QUERY_DELAY = 10.0


def fetch_recent_papers(cutoff: datetime) -> list[dict]:
    """Fetch recent RecSys & LLM papers from arxiv since *cutoff*."""
    client = arxiv.Client(page_size=100, delay_seconds=5.0, num_retries=5)

    seen_ids: set[str] = set()
    papers: list[dict] = []

    for qi, query in enumerate(SEARCH_QUERIES):
        log.info("ArXiv query %d/%d: %s", qi + 1, len(SEARCH_QUERIES), query)

        try:
            search = arxiv.Search(
                query=query,
                max_results=500,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending,
            )
            for result in client.results(search):
                paper_id = result.entry_id.split("/abs/")[-1]
                # Strip version suffix (e.g., v1, v2) for consistent dedup
                paper_id = re.sub(r"v\d+$", "", paper_id)
                if paper_id in seen_ids:
                    continue
                seen_ids.add(paper_id)

                # Use `published` (original submission date) for filtering,
                # matching the sort order (SubmittedDate).
                paper_date = result.published
                if paper_date.tzinfo is None:
                    paper_date = paper_date.replace(tzinfo=timezone.utc)
                if paper_date < cutoff:
                    break  # Sorted descending by SubmittedDate, so stop here

                papers.append(
                    {
                        "id": paper_id,
                        "title": result.title.replace("\n", " ").strip(),
                        "authors": [a.name for a in result.authors],
                        "abstract": result.summary.replace("\n", " ").strip(),
                        "categories": list(result.categories),
                        "published": result.published.strftime("%Y-%m-%d"),
                        "url": result.entry_id,
                        "pdf_url": result.pdf_url,
                        "comment": (result.comment or "").replace("\n", " ").strip(),
                        "source": "arxiv",
                    }
                )
        except arxiv.HTTPError as e:
            log.warning("ArXiv rate-limited on query %d/%d (HTTP %s), skipping: %s",
                        qi + 1, len(SEARCH_QUERIES), e.status, query)
        except Exception as e:
            log.warning("ArXiv query %d/%d failed (%s), skipping: %s",
                        qi + 1, len(SEARCH_QUERIES), e, query)

        # Wait between queries to respect ArXiv rate limits
        if qi < len(SEARCH_QUERIES) - 1:
            log.info("Waiting %.0fs before next query...", QUERY_DELAY)
            time.sleep(QUERY_DELAY)

    log.info("Fetched %d unique papers since %s", len(papers), cutoff.date())
    return papers
