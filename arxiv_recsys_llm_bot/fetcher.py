"""Fetch recent RecSys & LLM papers from ArXiv."""

from datetime import datetime, timezone

import arxiv

from arxiv_recsys_llm_bot.config import SEARCH_QUERIES, log


def fetch_recent_papers(cutoff: datetime) -> list[dict]:
    """Fetch recent RecSys & LLM papers from arxiv since *cutoff*."""
    client = arxiv.Client(page_size=100, delay_seconds=3.0, num_retries=3)

    seen_ids: set[str] = set()
    papers: list[dict] = []

    for query in SEARCH_QUERIES:
        log.info("ArXiv query: %s", query)
        search = arxiv.Search(
            query=query,
            max_results=100,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        for result in client.results(search):
            paper_id = result.entry_id.split("/abs/")[-1]
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
                }
            )

    log.info("Fetched %d unique papers since %s", len(papers), cutoff.date())
    return papers
