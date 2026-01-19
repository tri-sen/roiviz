"""
Normalized amino-acid property scales.

Policy:
- HR and PR are min-max normalized to [0,1] over the scale itself.
- Unknowns / non-standard letters are not included.
"""

from __future__ import annotations


def _minmax_normalize(scale: dict[str, float]) -> dict[str, float]:
    vals = list(scale.values())
    mn = min(vals)
    mx = max(vals)
    denom = (mx - mn) if (mx - mn) != 0 else 1.0
    return {aa: (v - mn) / denom for aa, v in scale.items()}


# Raw Kyte-Doolittle hydropathy
_RAW_HP: dict[str, float] = {
    "A": 1.8,
    "R": -4.5,
    "N": -3.5,
    "D": -3.5,
    "C": 2.5,
    "Q": -3.5,
    "E": -3.5,
    "G": -0.4,
    "H": -3.2,
    "I": 4.5,
    "L": 3.8,
    "K": -3.9,
    "M": 1.9,
    "F": 2.8,
    "P": -1.6,
    "S": -0.8,
    "T": -0.7,
    "W": -0.9,
    "Y": -1.3,
    "V": 4.2,
}

# polar requirement (common 20 AA set)
_RAW_PR: dict[str, float] = {
    "A": 7.0,
    "R": 9.1,
    "N": 10.0,
    "D": 13.0,
    "C": 4.8,
    "Q": 8.6,
    "E": 12.5,
    "G": 7.9,
    "H": 8.4,
    "I": 4.9,
    "L": 4.9,
    "K": 10.1,
    "M": 5.3,
    "F": 5.0,
    "P": 6.6,
    "S": 7.5,
    "T": 6.6,
    "W": 5.2,
    "Y": 5.4,
    "V": 5.6,
}

# Min-max normalized lookups used everywhere downstream
HP: dict[str, float] = _minmax_normalize(_RAW_HP)
PR: dict[str, float] = _minmax_normalize(_RAW_PR)

HP_ID = "hp"
PR_ID = "pr"
