# arxiv-recsys-llm-bot

A daily digest bot that fetches recommendation systems and LLM research papers from ArXiv, uses Gemini to identify industry papers, and emails a formatted summary.

## What it does

1. **Fetches papers** from ArXiv across multiple search queries (recsys, collaborative filtering, CTR prediction, learning to rank, information retrieval, LLM + recommendations/ranking/retrieval, RAG, dense retrieval, generative retrieval, neural IR)
2. **Classifies papers** as industry vs. academia using Gemini — identifies specific company names from author recognition and paper content signals (production deployments, A/B tests, proprietary datasets, etc.)
3. **Generates summaries** for industry papers highlighting key contributions
4. **Sends an HTML email** with the daily digest and saves reports locally

## Setup

### Requirements

- Python 3.12+
- A [Google Gemini API key](https://aistudio.google.com/apikey)
- A Gmail account with an [App Password](https://myaccount.google.com/apppasswords) (for email delivery)

### Install

```bash
pip install -r requirements.txt
```

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `GMAIL_APP_PASSWORD` | For email | Gmail App Password |
| `SENDER_EMAIL` | For email | Gmail address to send from |
| `RECIPIENT_EMAIL` | For email | Email address to send to |
| `GEMINI_MODEL` | No | Model name (default: `gemini-2.5-flash`) |
| `MAX_GEMINI_CALLS` | No | Hard cap on API calls (default: `80`) |
| `BATCH_SIZE` | No | Papers per Gemini batch (default: `10`) |

## Usage

```bash
# Full run — fetch, classify, summarize, email
python daily_recsys_llm_bot.py

# Or as a module
python -m arxiv_recsys_llm_bot

# Dry run — no email, no state update
python daily_recsys_llm_bot.py --dry-run

# Save report locally, skip email
python daily_recsys_llm_bot.py --no-email

# Override lookback period
python daily_recsys_llm_bot.py --lookback-days 5
```

## Automated daily runs

The included GitHub Actions workflow (`.github/workflows/daily_digest.yml`) runs the bot daily at 16:07 UTC. Add your secrets in the repository settings under **Settings > Secrets and variables > Actions**:

- `GEMINI_API_KEY`
- `GMAIL_APP_PASSWORD`
- `SENDER_EMAIL`
- `RECIPIENT_EMAIL`

## Project structure

```
arxiv_recsys_llm_bot/
├── config.py      # Environment variables, search queries, constants
├── state.py       # Run state management (no gap dates between runs)
├── fetcher.py     # ArXiv paper fetching
├── gemini.py      # Gemini classification + summary generation
├── formatter.py   # HTML email formatting
├── output.py      # Email sending + local report saving
└── main.py        # Pipeline orchestration + CLI
```

`daily_recsys_llm_bot.py` is a thin entry point that delegates to the package.

Reports are saved to `reports/` as both HTML and JSON on every run.
