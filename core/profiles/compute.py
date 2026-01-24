"""
Compute profiles over alignment columns.

Required for Plot 1/2:
- pairwise |ΔHP| and |ΔPR| per column (per pair)
- median + P25/P75 of |Δ| per column

GAP handling:
- GAP ('-' or '.') is treated as value 0.0 for HP/PR mapping.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.models import AlignmentResult, ComputedProfiles


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _quantile(sorted_vals: list[float], q: float) -> float:
    n = len(sorted_vals)
    if n == 0:
        raise ValueError("quantile of empty list")
    if n == 1:
        return sorted_vals[0]
    pos = (n - 1) * q
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def _median_p25_p75(vals: list[float]) -> tuple[float, float, float]:
    s = sorted(vals)
    med = _quantile(s, 0.5)
    p25 = _quantile(s, 0.25)
    p75 = _quantile(s, 0.75)
    return med, p25, p75


def _alignment_length(seqs: list[str]) -> int:
    lengths = {len(s) for s in seqs}
    if len(lengths) != 1:
        raise ValueError("Inconsistent aligned sequence lengths.")
    return next(iter(lengths))


def _pair_key(a: str, b: str) -> str:
    return f"{a}__vs__{b}"


def compute_profiles_from_alignment(
    *,
    alignment: AlignmentResult,
    hp_scale: dict[str, float],
    pr_scale: dict[str, float],
    hp_scale_id: str = "hp",
    pr_scale_id: str = "pr",
) -> ComputedProfiles:
    seqs = [s.aligned_sequence for s in alignment.sequences]
    names = [s.name for s in alignment.sequences]

    L = _alignment_length(seqs)
    n = len(seqs)
    positions = list(range(1, L + 1))

    # Per-seq mapped values (float in [0,1] or None), GAP treated as 0.0
    hp_per_seq: dict[str, list[float | None]] = {name: [None] * L for name in names}
    pr_per_seq: dict[str, list[float | None]] = {name: [None] * L for name in names}

    # Composition
    seen_chars: set[str] = set()
    for s in seqs:
        seen_chars.update(set(s))

    residues = sorted([c for c in seen_chars if (c == "-" or ("A" <= c <= "Z"))])
    composition_fraction: dict[str, list[float]] = {r: [0.0] * L for r in residues}
    gap_fraction: list[float] = [0.0] * L

    # Map per-seq values + composition
    for col in range(L):
        col_chars = [seq[col] for seq in seqs]

        for c in col_chars:
            if c in composition_fraction:
                composition_fraction[c][col] += 1.0

        for r in residues:
            composition_fraction[r][col] /= float(n)

        gap_fraction[col] = composition_fraction.get("-", [0.0] * L)[col]

        for name, seq in zip(names, seqs):
            aa = seq[col].upper()

            if aa in {"-", "."}:
                hp_per_seq[name][col] = 0.0
                pr_per_seq[name][col] = 0.0
                continue

            hp_per_seq[name][col] = hp_scale.get(aa)
            pr_per_seq[name][col] = pr_scale.get(aa)

    # Pairwise |Δ|
    hp_pairwise_delta: dict[str, list[float | None]] = {}
    pr_pairwise_delta: dict[str, list[float | None]] = {}

    for i in range(n):
        for j in range(i + 1, n):
            a = names[i]
            b = names[j]
            key = _pair_key(a, b)

            hp_d: list[float | None] = [None] * L
            pr_d: list[float | None] = [None] * L

            ha = hp_per_seq[a]
            hb = hp_per_seq[b]
            pa = pr_per_seq[a]
            pb = pr_per_seq[b]

            for col in range(L):
                va = ha[col]
                vb = hb[col]
                if va is not None and vb is not None:
                    hp_d[col] = abs(va - vb)

                va2 = pa[col]
                vb2 = pb[col]
                if va2 is not None and vb2 is not None:
                    pr_d[col] = abs(va2 - vb2)

            hp_pairwise_delta[key] = hp_d
            pr_pairwise_delta[key] = pr_d

    # Per-column summary over pairwise |Δ|
    hp_delta_median: list[float | None] = [None] * L
    hp_delta_p25: list[float | None] = [None] * L
    hp_delta_p75: list[float | None] = [None] * L

    pr_delta_median: list[float | None] = [None] * L
    pr_delta_p25: list[float | None] = [None] * L
    pr_delta_p75: list[float | None] = [None] * L

    hp_pairs = list(hp_pairwise_delta.values())
    pr_pairs = list(pr_pairwise_delta.values())

    for col in range(L):
        hp_vals = [arr[col] for arr in hp_pairs if arr[col] is not None]
        pr_vals = [arr[col] for arr in pr_pairs if arr[col] is not None]

        if hp_vals:
            med, p25, p75 = _median_p25_p75(hp_vals)
            hp_delta_median[col], hp_delta_p25[col], hp_delta_p75[col] = med, p25, p75

        if pr_vals:
            med, p25, p75 = _median_p25_p75(pr_vals)
            pr_delta_median[col], pr_delta_p25[col], pr_delta_p75[col] = med, p25, p75

    return ComputedProfiles(
        computed_at=_utc_now(),
        alignment_length=L,
        aa_position=positions,
        hp_scale_id=hp_scale_id,
        pr_scale_id=pr_scale_id,
        hp_per_seq=hp_per_seq,
        pr_per_seq=pr_per_seq,
        hp_pairwise_delta=hp_pairwise_delta,
        pr_pairwise_delta=pr_pairwise_delta,
        hp_delta_median=hp_delta_median,
        hp_delta_p25=hp_delta_p25,
        hp_delta_p75=hp_delta_p75,
        pr_delta_median=pr_delta_median,
        pr_delta_p25=pr_delta_p25,
        pr_delta_p75=pr_delta_p75,
        gap_fraction=gap_fraction,
        composition_fraction=composition_fraction,
        method_name="profiles_v1",
        method_version="0.1",
    )
