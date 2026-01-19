"""
Validation and normalization utilities (pure functions).

Rules:
- No Streamlit imports.
- No side effects.
- Keep validation strict enough for MVP, but not fragile.

MVP policy:
- Accept letters A–Z (uppercase after normalization).
- Disallow gaps '-' and stop '*' in raw (unaligned) input.
- Whitespace/newlines are stripped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_ALLOWED_AA_RE = re.compile(r"^[A-Z]+$")


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    normalized: str
    error: str | None = None


def normalize_text(s: str) -> str:
    return (s or "").strip()


def normalize_aa_sequence(raw: str) -> str:
    # Remove whitespace/newlines and uppercase
    s = (raw or "").strip().upper()
    s = "".join(s.split())
    return s


def validate_name(raw: str) -> ValidationResult:
    name = normalize_text(raw)
    if not name:
        return ValidationResult(False, "", "Name is required.")
    if len(name) > 80:
        return ValidationResult(False, name, "Name is too long (max 80 characters).")
    return ValidationResult(True, name, None)


def validate_aa_sequence(raw: str) -> ValidationResult:
    s = normalize_aa_sequence(raw)
    if not s:
        return ValidationResult(False, "", "Sequence is required.")
    if "-" in s:
        return ValidationResult(False, s, "Gaps '-' are not allowed in raw input (unaligned).")
    if "*" in s:
        return ValidationResult(False, s, "Stop '*' is not allowed in AA input for this MVP.")
    if not _ALLOWED_AA_RE.match(s):
        return ValidationResult(False, s, "Invalid characters. Allowed: letters A–Z only (whitespace is ignored).")
    if len(s) < 2:
        return ValidationResult(False, s, "Sequence is too short.")
    return ValidationResult(True, s, None)
