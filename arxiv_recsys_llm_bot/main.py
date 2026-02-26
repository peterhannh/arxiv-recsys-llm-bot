"""Main pipeline orchestration."""

import argparse
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from google import genai

from arxiv_recsys_llm_bot.config import GEMINI_API_KEY, MAX_GEMINI_CALLS, log
from arxiv_recsys_llm_bot.dedup import deduplicate_papers
from arxiv_recsys_llm_bot.fetcher import fetch_recent_papers
from arxiv_recsys_llm_bot.formatter import format_email_html
from arxiv_recsys_llm_bot.gemini import classify_papers_with_gemini, generate_summaries
from arxiv_recsys_llm_bot.huggingface import fetch_huggingface_papers
from arxiv_recsys_llm_bot.output import save_report, send_email
from arxiv_recsys_llm_bot.semantic_scholar import fetch_semantic_scholar_papers
from arxiv_recsys_llm_bot.state import get_lookback_cutoff, save_state


def main():
    parser = argparse.ArgumentParser(description="Daily ArXiv RecSys & LLM Industry Bot")
    parser.add_argument(
        "--lookback-days", type=int, default=None,
        help="Override: how many days back to search (default: auto from state.json)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and classify but don't send email (save locally only)",
    )
    parser.add_argument(
        "--no-email", action="store_true",
        help="Skip sending email, just save report locally",
    )
    parser.add_argument(
        "--max-gemini-calls", type=int, default=MAX_GEMINI_CALLS,
        help=f"Max Gemini API calls (default: {MAX_GEMINI_CALLS})",
    )
    args = parser.parse_args()

    # Validate required config
    if not GEMINI_API_KEY:
        log.error("GEMINI_API_KEY environment variable is required.")
        sys.exit(1)

    call_counter = {"count": 0}
    max_calls = args.max_gemini_calls

    log.info("=== ArXiv RecSys & LLM Industry Bot ===")

    # Determine cutoff date (state-aware, no gaps)
    cutoff = get_lookback_cutoff(args.lookback_days)

    # 1a. Fetch papers from ArXiv
    log.info("Step 1a: Fetching papers from ArXiv...")
    arxiv_papers = fetch_recent_papers(cutoff)

    # 1b. Fetch papers from Semantic Scholar
    log.info("Step 1b: Fetching papers from Semantic Scholar...")
    s2_papers = fetch_semantic_scholar_papers(cutoff)

    # 1c. Fetch papers from HuggingFace Daily Papers
    log.info("Step 1c: Fetching papers from HuggingFace Daily Papers...")
    hf_papers = fetch_huggingface_papers()

    # 1d. Combine + deduplicate (ArXiv first for richest metadata, then S2, then HF)
    log.info("Step 1d: Deduplicating papers...")
    all_raw = arxiv_papers + s2_papers + hf_papers
    log.info("Pre-dedup counts: ArXiv=%d, S2=%d, HF=%d, total=%d",
             len(arxiv_papers), len(s2_papers), len(hf_papers), len(all_raw))
    papers = deduplicate_papers(all_raw)

    if not papers:
        log.info("No papers found since cutoff. State NOT updated (will retry same window next run).")
        return

    # 2. Classify with Gemini
    log.info("Step 2: Classifying %d papers with Gemini...", len(papers))
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    classify_papers_with_gemini(papers, gemini_client, call_counter, max_calls)

    industry_papers = [p for p in papers if p.get("classification") == "industry"]
    log.info(
        "Classification results: %d industry, %d academia, %d unknown",
        len(industry_papers),
        sum(1 for p in papers if p.get("classification") == "academia"),
        sum(1 for p in papers if p.get("classification") == "unknown"),
    )

    # 3. Generate summaries for industry papers
    if industry_papers:
        log.info("Step 3: Generating summaries for %d industry papers...", len(industry_papers))
        generate_summaries(industry_papers, gemini_client, call_counter, max_calls)

    log.info("Total Gemini API calls used: %d / %d", call_counter["count"], max_calls)

    # 4. Format email
    log.info("Step 4: Formatting email...")
    html_report = format_email_html(industry_papers, len(papers), cutoff)

    # 5. Save locally (always)
    report_path = save_report(html_report, industry_papers)

    # 6. Send email
    if not args.dry_run and not args.no_email:
        today = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%b %d")
        subject = f"RecSys & LLM Industry Papers - {today} ({len(industry_papers)} papers)"
        if send_email(html_report, subject):
            log.info("Done! Check your inbox.")
        else:
            log.info("Email not sent. Report saved at: %s", report_path)
    else:
        log.info("Dry run / no-email mode. Report saved at: %s", report_path)

    # 7. Update state (only on non-dry-run)
    if not args.dry_run:
        save_state({
            "last_run_date": datetime.now(timezone.utc).isoformat(),
            "last_run_papers": len(papers),
            "last_run_industry": len(industry_papers),
        })
        log.info("State updated: next run will pick up from %s", datetime.now(timezone.utc).date())

    # Print quick summary to stdout
    s2_only = sum(1 for p in papers if p.get("source") == "s2")
    hf_count = sum(1 for p in papers if "hf" in p.get("source", ""))
    print(f"\n{'='*60}")
    print(f"  {len(industry_papers)} industry papers found (out of {len(papers)} total)")
    print(f"  Sources: ArXiv={len(arxiv_papers)}, S2={len(s2_papers)}, HF={len(hf_papers)} (pre-dedup)")
    print(f"  After dedup: {len(papers)} unique | S2-only: {s2_only} | HF-trending: {hf_count}")
    print(f"  Gemini API calls: {call_counter['count']} / {max_calls}")
    print(f"  Report: {report_path}")
    print(f"{'='*60}\n")

    for p in industry_papers:
        company = p.get("company", "")
        label = f"[{company}]" if company else "[industry]"
        print(f"  {label} {p['title']}")
        print(f"    {p['url']}\n")
