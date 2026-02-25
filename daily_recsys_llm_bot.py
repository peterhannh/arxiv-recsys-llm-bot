#!/usr/bin/env python3
"""
Daily ArXiv RecSys & LLM Bot — entry point.

This thin wrapper delegates to the arxiv_recsys_llm_bot package.
Can also be run as:  python -m arxiv_recsys_llm_bot
"""

from arxiv_recsys_llm_bot.main import main

if __name__ == "__main__":
    main()
