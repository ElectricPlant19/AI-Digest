"""Centralized env var loading and validation.

Loads a local `.env` file if present (no-op in GitHub Actions) and fails
fast with a clear message when required variables are missing. Values are
never printed — only variable names.
"""
import os
import sys

from dotenv import load_dotenv


REQUIRED = ["OPENROUTER_API_KEY", "RESEND_API_KEY", "DIGEST_TO_EMAIL"]
OPTIONAL = ["DIGEST_FROM_EMAIL", "TAVILY_API_KEY"]


def load_config() -> dict:
    load_dotenv()

    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        print(
            f"ERROR: missing required env vars: {', '.join(missing)}",
            file=sys.stderr,
        )
        print(
            "Set them in your environment or a local .env file (see .env.example).",
            file=sys.stderr,
        )
        sys.exit(1)

    return {k: os.environ.get(k) for k in REQUIRED + OPTIONAL}
