"""Prompt injection detection and input sanitization."""

import re

from src.utils.logger import get_logger

logger = get_logger(__name__)

_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|above)\s+(instructions|prompts|context)",
    r"disregard\s+(previous|all|your)",
    r"system\s*[:\-]\s*override",
    r"\[system\]",
    r"<system>",
    r"you\s+are\s+now",
    r"pretend\s+to\s+be",
    r"act\s+as\s+if",
    r"forget\s+(everything|all|your)",
    r"new\s+instructions?\s*:",
    r"override\s+(compliance|rules|safety)",
    r"mark\s+as\s+compliant",
    r"change\s+verdict\s+to",
    r"set\s+overcharge\s+to\s+0",
    # Unicode obfuscation patterns
    r"[\u200b-\u200d\ufeff]",        # Zero-width characters
    r"[\u202a-\u202e]",              # Bidirectional override chars
    r"\\u[0-9a-fA-F]{4}",           # Unicode escape sequences in text
    r"[\u2066-\u2069]",             # Bidi isolate characters
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def detect_prompt_injection(text: str) -> bool:
    """Returns True if text contains suspected prompt injection."""
    for pattern in _COMPILED:
        if pattern.search(text):
            logger.warning("Prompt injection detected: matched pattern")
            return True
    return False


def sanitize_input(text: str, max_length: int = 5000) -> str:
    """Sanitize user/scraped input before sending to LLM."""
    if not text:
        return ""
    text = text[:max_length]
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)  # Control chars
    text = re.sub(r"[\u200b-\u200d\ufeff\u202a-\u202e\u2066-\u2069]", "", text)  # Hidden Unicode

    if detect_prompt_injection(text):
        raise ValueError("Input rejected: suspected prompt injection")

    return text.strip()


def sanitize_error(error: Exception, max_length: int = 200) -> str:
    """Sanitize error messages to avoid leaking secrets."""
    msg = str(error)[:max_length]
    msg = re.sub(r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_KEY]", msg)
    msg = re.sub(r"gsk_[a-zA-Z0-9]{20,}", "[REDACTED_KEY]", msg)
    msg = re.sub(r"Bearer\s+[a-zA-Z0-9._-]+", "Bearer [REDACTED]", msg)
    msg = re.sub(r"/home/[^\s]+", "[PATH]", msg)
    msg = re.sub(r"/Users/[^\s]+", "[PATH]", msg)
    return msg
