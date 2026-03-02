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

# Semantic Scholar API key (optional — works without it but rate limits are lower)
S2_API_KEY = os.environ.get("S2_API_KEY", "")

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
    # --- Primary: fetch ALL cs.IR papers, let Gemini filter for relevance ---
    "cat:cs.IR",

    # --- Catch RecSys papers filed under other categories (cs.LG, cs.CL, cs.AI) ---
    'all:"recommendation system" OR all:"recommender system"',
    'all:"collaborative filtering"',
    'all:"click-through rate" OR all:"CTR prediction"',
    'all:"generative recommendation" OR all:"generative retrieval"',
    'all:"large language model" AND all:"recommendation"',
]

# ---------------------------------------------------------------------------
# Semantic Scholar search queries (broader text search, fewer queries needed)
# ---------------------------------------------------------------------------
S2_SEARCH_QUERIES = [
    "recommendation system OR recommender system",
    "collaborative filtering OR click-through rate prediction",
    "learning to rank",
    "large language model recommendation OR LLM ranking",
    "LLM reranking OR generative recommendation",
    "large language model information retrieval OR generative retrieval",
]

# ---------------------------------------------------------------------------
# HuggingFace Daily Papers — relevance filter keywords
# ---------------------------------------------------------------------------
HF_RELEVANCE_KEYWORDS = {
    "recommendation", "recommender", "recsys",
    "collaborative filtering", "click-through", "ctr",
    "learning to rank", "reranking", "re-ranking",
    "information retrieval", "generative retrieval",
    "ranking", "retrieval",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("arxiv_recsys_llm_bot")
