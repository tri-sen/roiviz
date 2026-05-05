from __future__ import annotations

STANDARD_AMINO_ACIDS: tuple[str, ...] = (
    "A", "C", "D", "E", "F", "G", "H", "I", "K", "L",
    "M", "N", "P", "Q", "R", "S", "T", "V", "W", "Y",
)

GAP_CHAR: str = "-"

# Kyte & Doolittle, 1982
HYDROPATHY_RAW: dict[str, float] = {
    "A":  1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C":  2.5,
    "Q": -3.5, "E": -3.5, "G": -0.4, "H": -3.2, "I":  4.5,
    "L":  3.8, "K": -3.9, "M":  1.9, "F":  2.8, "P": -1.6,
    "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V":  4.2,
}

# min-max normalization: (v - min) / (max - min); for KD: min=-4.5, max=4.5, range=9.0
_KD_MIN: float = min(HYDROPATHY_RAW.values())
_KD_MAX: float = max(HYDROPATHY_RAW.values())
NORMALIZED_HYDROPATHY: dict[str, float] = {
    aa: (v - _KD_MIN) / (_KD_MAX - _KD_MIN)
    for aa, v in HYDROPATHY_RAW.items()
}

# Mathew & Luthey-Schulten, 2008
POLAR_REQUIREMENT_RAW: dict[str, float] = {
    "A":  6.5,
    "R":  8.6,
    "N":  9.6,
    "D": 12.2,
    "C":  4.3,
    "Q":  8.9,
    "E": 13.6,
    "G":  9.0,
    "H":  7.9,
    "I":  5.0,
    "L":  4.4,
    "K": 10.2,
    "M":  5.0,
    "F":  4.5,
    "P":  6.1,
    "S":  7.5,
    "T":  6.2,
    "W":  4.9,
    "Y":  7.7,
    "V":  6.2,
}

# min-max normalization: (v - min) / (max - min)
_PR_MIN: float = min(POLAR_REQUIREMENT_RAW.values())
_PR_MAX: float = max(POLAR_REQUIREMENT_RAW.values())
NORMALIZED_POLAR_REQUIREMENT: dict[str, float] = {
    aa: (v - _PR_MIN) / (_PR_MAX - _PR_MIN)
    for aa, v in POLAR_REQUIREMENT_RAW.items()
}

MAFFT_OUTPUT_CAP: int = 50_000

# Okabe-Ito colorblind-safe palette
PALETTES: dict[str, tuple[str, ...]] = {
    "default": (
        "#E69F00",
        "#56B4E9",
        "#009E73",
        "#F0E442",
        "#0072B2",
        "#D55E00",
        "#CC79A7",
        "#000000",
    ),
}

GAP_COLOR: str = "#AAAAAA"
DEFAULT_REGION_ANNOTATION_COLOR: str = "#636EFA"

AMINO_ACID_THREE_LETTER: dict[str, str] = {
    "A": "Ala", "C": "Cys", "D": "Asp", "E": "Glu", "F": "Phe",
    "G": "Gly", "H": "His", "I": "Ile", "K": "Lys", "L": "Leu",
    "M": "Met", "N": "Asn", "P": "Pro", "Q": "Gln", "R": "Arg",
    "S": "Ser", "T": "Thr", "V": "Val", "W": "Trp", "Y": "Tyr",
}


AMINO_ACID_COLOR_PALETTES: dict[str, dict[str, str]] = {
    "zappo_physicochemical": {
        "I": "#FF99CC", "L": "#FF99CC", "V": "#FF99CC", "A": "#FF99CC", "M": "#FF99CC",
        "F": "#FFA500", "W": "#FFA500", "Y": "#FFA500",
        "K": "#00008B", "R": "#00008B", "H": "#00008B",
        "D": "#FF0000", "E": "#FF0000",
        "S": "#90EE90", "T": "#90EE90", "N": "#90EE90", "Q": "#90EE90",
        "P": "#FF00FF", "G": "#FF00FF",
        "C": "#FFFF00",
        "-": "#D9D9D9",
    },
    "weblogo_hydrophobicity": {
        "R": "#0000FF", "K": "#0000FF", "D": "#0000FF", "E": "#0000FF",
        "N": "#0000FF", "Q": "#0000FF",
        "S": "#008000", "G": "#008000", "H": "#008000", "T": "#008000",
        "A": "#008000", "P": "#008000",
        "Y": "#000000", "V": "#000000", "M": "#000000", "C": "#000000",
        "L": "#000000", "F": "#000000", "I": "#000000", "W": "#000000",
        "-": "#D9D9D9",
    },
    "charge": {
        "K": "#0000FF", "R": "#0000FF", "H": "#0000FF",
        "D": "#FF0000", "E": "#FF0000",
        "A": "#808080", "C": "#808080", "F": "#808080", "G": "#808080",
        "I": "#808080", "L": "#808080", "M": "#808080", "N": "#808080",
        "P": "#808080", "Q": "#808080", "S": "#808080", "T": "#808080",
        "V": "#808080", "W": "#808080", "Y": "#808080",
        "-": "#D9D9D9",
    },
}

AMINO_ACID_COLOR_PALETTE_LABELS: dict[str, str] = {
    "zappo_physicochemical": "Physicochemical / Zappo-style",
    "weblogo_hydrophobicity": "WebLogo hydrophobicity",
    "charge": "Charge",
}

DEFAULT_AMINO_ACID_COLOR_PALETTE: str = "zappo_physicochemical"


if __name__ == "__main__":
    assert len(STANDARD_AMINO_ACIDS) == 20
    assert GAP_CHAR == "-"
    assert all(0 <= v <= 1 for v in NORMALIZED_HYDROPATHY.values())
    print("Constants OK")
