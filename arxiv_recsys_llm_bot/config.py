"""Configuration: environment variables, constants, and search queries."""

import logging
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Environment-based configuration (no hardcoded secrets)
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

# Max Gemini API calls allowed (hard cap)
MAX_GEMINI_CALLS = int(os.environ.get("MAX_GEMINI_CALLS", "80"))

# Papers per Gemini batch (to minimise API calls)
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "10"))

# State file for tracking last run (no gap dates)
STATE_FILE = Path(__file__).resolve().parent.parent / "state.json"

# ---------------------------------------------------------------------------
# ArXiv search queries — RecSys + LLM research
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    # --- Recommendation Systems ---
    'all:"recommendation system" OR all:"recommender system"',
    'all:"collaborative filtering"',
    'all:"click-through rate" OR all:"CTR prediction"',
    'all:"learning to rank"',
    'all:"information retrieval" AND cat:cs.IR',

    # --- LLM + RecSys / Ranking / Retrieval ---
    'all:"large language model" AND all:"recommendation"',
    'all:"LLM" AND all:"ranking"',
    'all:"large language model" AND all:"retrieval"',

    # --- RAG & Generative Retrieval ---
    'all:"retrieval-augmented generation"',
    'all:"generative retrieval"',

    # --- Dense / Neural Retrieval ---
    'all:"dense retrieval"',
    'all:"neural information retrieval"',

    # --- LLM as Judge / Evaluator for ranking ---
    'all:"LLM" AND all:"relevance" AND all:"search"',
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("arxiv_recsys_llm_bot")
