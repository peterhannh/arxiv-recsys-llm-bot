"""HTML email formatting."""

import html
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def format_email_html(
    industry_papers: list[dict],
    all_papers_count: int,
    cutoff: datetime,
) -> str:
    """Create a nicely formatted HTML email."""
    today = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%B %d, %Y")
    since = cutoff.strftime("%b %d")

    papers_html = ""
    for i, p in enumerate(industry_papers, 1):
        authors_raw = ", ".join(p["authors"][:8])
        if len(p["authors"]) > 8:
            authors_raw += f" ... (+{len(p['authors']) - 8} more)"

        # HTML-escape all user-controlled strings
        title_safe = html.escape(p["title"])
        authors_safe = html.escape(authors_raw)
        company_safe = html.escape(p.get("company", ""))
        summary_safe = html.escape(p.get("summary", ""))
        categories_safe = html.escape(", ".join(p.get("categories", [])))
        published_safe = html.escape(p.get("published", ""))
        url_safe = html.escape(p.get("url", ""))
        pdf_safe = html.escape(p.get("pdf_url", p.get("url", "")))

        # Company badge — shown prominently when available
        company_html = ""
        if company_safe:
            company_html = (
                f'<span style="background: #fef3c7; color: #92400e; font-size: 11px;'
                f' padding: 2px 8px; border-radius: 10px; margin-left: 4px;'
                f' font-weight: 600;">{company_safe}</span>'
            )

        papers_html += f"""
        <tr>
            <td style="padding: 16px 20px; border-bottom: 1px solid #e5e7eb;">
                <div style="margin-bottom: 6px;">
                    <span style="background: #dbeafe; color: #1e40af; font-size: 11px;
                                 padding: 2px 8px; border-radius: 10px; font-weight: 600;">
                        #{i}
                    </span>
                    {company_html}
                </div>
                <a href="{url_safe}" style="color: #1d4ed8; text-decoration: none;
                          font-size: 16px; font-weight: 600; line-height: 1.4;">
                    {title_safe}
                </a>
                <div style="color: #6b7280; font-size: 13px; margin-top: 4px;">
                    {authors_safe}
                </div>
                <div style="color: #9ca3af; font-size: 12px; margin-top: 2px;">
                    {published_safe} &middot; {categories_safe}
                </div>
                {f'<div style="color: #374151; font-size: 14px; margin-top: 8px; line-height: 1.5;">{summary_safe}</div>' if summary_safe else ''}
                <div style="margin-top: 8px;">
                    <a href="{url_safe}" style="color: #6366f1; font-size: 12px;
                              text-decoration: none; margin-right: 12px;">Abstract</a>
                    <a href="{pdf_safe}" style="color: #6366f1;
                              font-size: 12px; text-decoration: none;">PDF</a>
                </div>
            </td>
        </tr>"""

    if not papers_html:
        papers_html = """
        <tr>
            <td style="padding: 32px 20px; text-align: center; color: #9ca3af;">
                No industry papers found in this period.
            </td>
        </tr>"""

    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin: 0; padding: 0; background: #f3f4f6; font-family:
             -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background: #f3f4f6;
       padding: 24px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background: #ffffff;
       border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">

    <!-- Header -->
    <tr>
        <td style="background: linear-gradient(135deg, #4f46e5, #7c3aed);
                   padding: 28px 24px; text-align: center;">
            <div style="color: #ffffff; font-size: 22px; font-weight: 700;">
                RecSys &amp; LLM Industry Papers
            </div>
            <div style="color: #c4b5fd; font-size: 14px; margin-top: 4px;">
                {today} &middot; Since {since}
            </div>
        </td>
    </tr>

    <!-- Stats bar -->
    <tr>
        <td style="padding: 14px 20px; background: #fafafa;
                   border-bottom: 1px solid #e5e7eb;">
            <table width="100%"><tr>
                <td style="color: #6b7280; font-size: 13px;">
                    <strong style="color: #111827; font-size: 20px;">
                        {len(industry_papers)}</strong> industry papers
                </td>
                <td style="color: #6b7280; font-size: 13px; text-align: right;">
                    out of <strong>{all_papers_count}</strong> total papers
                </td>
            </tr></table>
        </td>
    </tr>

    <!-- Papers -->
    {papers_html}

    <!-- Footer -->
    <tr>
        <td style="padding: 20px; text-align: center; color: #9ca3af;
                   font-size: 12px; border-top: 1px solid #e5e7eb;">
            Generated by arxiv-recsys-llm-bot &middot;
            <a href="https://arxiv.org/list/cs.IR/recent"
               style="color: #6366f1; text-decoration: none;">Browse cs.IR</a>
            &middot;
            <a href="https://arxiv.org/list/cs.CL/recent"
               style="color: #6366f1; text-decoration: none;">Browse cs.CL</a>
        </td>
    </tr>

</table>
</td></tr></table>
</body>
</html>"""
