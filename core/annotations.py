# core/annotations.py
"""
Pure helpers for annotation features (no Streamlit imports).

Includes:
- RegionalAnnotation DTO
- AminoAcidNote DTO
- lane assignment (deterministic greedy)
- amino-acid key normalization + 1-letter -> 3-letter lowercase mapping
- per-position amino-acid note block formatting (grouped per amino acid)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class RegionalAnnotation:
    """
    Interval annotation in alignment coordinates (1-based, inclusive).

    start/end are inclusive positions on the alignment x-axis.
    """
    start: int
    end: int
    text: str
    ann_id: str
    color: str | None = None


@dataclass(frozen=True, slots=True)
class AminoAcidNote:
    """One note entry for an amino acid."""
    note_id: str
    text: str


_AA_1_TO_3 = {
    "A": "ala",
    "C": "cys",
    "D": "asp",
    "E": "glu",
    "F": "phe",
    "G": "gly",
    "H": "his",
    "I": "ile",
    "K": "lys",
    "L": "leu",
    "M": "met",
    "N": "asn",
    "P": "pro",
    "Q": "gln",
    "R": "arg",
    "S": "ser",
    "T": "thr",
    "V": "val",
    "W": "trp",
    "Y": "tyr",
}


def normalize_aa_key(aa: str) -> str:
    """
    Normalize amino-acid key for internal dict use.

    Accepts:
    - one-letter A..Y
    - three-letter (e.g. "Val", "VAL", "val")
    - "-" / "gap"

    Returns:
    - "A".."Y" or "-" (gap)
    """
    raw = (aa or "").strip()
    if not raw:
        raise ValueError("Empty amino acid key")

    low = raw.lower()
    if low in {"-", "gap"}:
        return "-"

    up = raw.upper()
    if len(up) == 1 and up in _AA_1_TO_3:
        return up

    if len(low) == 3 and low.isalpha():
        for k, v in _AA_1_TO_3.items():
            if v == low:
                return k

    raise ValueError(f"Unsupported amino acid key: {aa!r}")


def one_letter_to_three_lower(aa: str) -> str:
    """
    Convert AA key to 3-letter lowercase for display.

    "-" / "gap" -> "gap"
    """
    k = normalize_aa_key(aa)
    if k == "-":
        return "gap"
    return _AA_1_TO_3[k]


def lane_assign(regions: Iterable[RegionalAnnotation]) -> list[tuple[RegionalAnnotation, int]]:
    """
    Deterministic greedy lane assignment to avoid overlaps per lane.

    Rule: place interval into first lane where start > last_end (gap=0),
    else create new lane.

    Determinism:
    - sort by (start, end, text, ann_id)
    """
    regs = list(regions)
    regs.sort(key=lambda r: (r.start, r.end, r.text, r.ann_id))

    lane_last_end: list[int] = []
    out: list[tuple[RegionalAnnotation, int]] = []

    for r in regs:
        placed = False
        for lane_idx, last_end in enumerate(lane_last_end):
            if r.start > last_end:
                lane_last_end[lane_idx] = r.end
                out.append((r, lane_idx))
                placed = True
                break
        if not placed:
            lane_last_end.append(r.end)
            out.append((r, len(lane_last_end) - 1))

    return out


def build_aa_note_block(
    *,
    occurring_symbols: Iterable[str],
    aa_annotations: dict[str, list[AminoAcidNote]],
) -> str:
    """
    Build the hover section for AA notes.

    - Groups by amino acid (3-letter lower-case heading).
    - Each note is a separate line (prefixed with "- ").

    Output HTML uses <br> (Plotly hover-safe).

    Always returns a block starting with:
      "Amino acid note: —"
    or:
      "Amino acid note:<br>val:<br>- note1<br>- note2<br>gly:<br>- note..."
    """
    occ_norm: set[str] = set()
    for s in occurring_symbols:
        try:
            occ_norm.add(normalize_aa_key(s))
        except ValueError:
            continue

    # Stable order: AA20 then gap
    order = list(_AA_1_TO_3.keys()) + ["-"]

    lines: list[str] = []
    for k in order:
        if k not in occ_norm:
            continue
        notes = aa_annotations.get(k, [])
        # filter empties defensively
        note_texts = [n.text.strip() for n in notes if n and n.text and n.text.strip()]
        if not note_texts:
            continue

        lines.append(f"{one_letter_to_three_lower(k)}:")
        for t in note_texts:
            lines.append(f"- {t}")

    if not lines:
        return "Amino acid note: —"
    return "Amino acid note:<br>" + "<br>".join(lines)
