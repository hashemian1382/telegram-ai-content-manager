"""Service layer package exporting scraping, drafting, and AI generation."""

import httpx

from .ai import generate_with_gemini, get_allowed_model_ids
from .drafts import (
    MAX_MESSAGE_LENGTH,
    create_direct_draft,
    create_random_draft,
    publish_draft,
    validate_text,
)
from .scraper import (
    normalize_channel,
    parse_datetime,
    run_scrape,
    scrape_channel,
    source_candidates,
)

__all__ = [
    "MAX_MESSAGE_LENGTH",
    "create_direct_draft",
    "create_random_draft",
    "generate_with_gemini",
    "get_allowed_model_ids",
    "httpx",
    "normalize_channel",
    "parse_datetime",
    "publish_draft",
    "run_scrape",
    "scrape_channel",
    "source_candidates",
    "validate_text",
]
