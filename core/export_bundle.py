# core/export_bundle.py
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from typing import Any, Iterable
import importlib


AA20 = list("ACDEFGHIKLMNPQRSTVWY")
GAP = "-"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_fasta(records: Iterable[tuple[str, str]]) -> str:
    lines: list[str] = []
    for name, seq in records:
        safe = (name or "sequence").strip().replace("\n", " ").replace("\r", " ")
        lines.append(f">{safe}")
        s = seq or ""
        for i in range(0, len(s), 80):
            lines.append(s[i : i + 80])
    return "\n".join(lines) + "\n"


def _event_to_dict(e: Any) -> dict[str, Any]:
    if isinstance(e, dict):
        return e
    to_dict = getattr(e, "to_dict", None)
    if callable(to_dict):
        d = to_dict()
        if isinstance(d, dict):
            return d
    return {"event": "unserializable_event", "data": {"repr": repr(e)}}


def _jsonl(events: list[Any]) -> str:
    lines = [json.dumps(_event_to_dict(e), ensure_ascii=False) for e in events]
    return "\n".join(lines) + ("\n" if lines else "")


def _write_csv(rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def _split_pair_key(pair_key: str) -> tuple[str, str]:
    if "__vs__" in pair_key:
        a, b = pair_key.split("__vs__", 1)
        return a, b
    if " vs " in pair_key:
        a, b = pair_key.split(" vs ", 1)
        return a, b
    return pair_key, "?"


def _slug(s: str) -> str:
    """
    Make names safe for CSV header columns.
    Keep it stable and readable.
    """
    s = (s or "seq").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "seq"


def _norm_sym(ch: str) -> str:
    c = (ch or "").upper()
    if c in {".", "-"}:
        return "-"
    return c


def _load_scales() -> tuple[dict[str, float], dict[str, float], str | None, str | None]:
    """
    Robustly load normalized scales from core.scales.

    Supported names:
      - preferred: HP_SCALE / PR_SCALE
      - fallback:  HP / PR

    Also returns optional IDs:
      - HP_ID / PR_ID if present
    """
    mod = importlib.import_module("core.profiles.scales")
    mod = importlib.reload(mod)

    hp = getattr(mod, "HP_SCALE", None) or getattr(mod, "HP", None)
    pr = getattr(mod, "PR_SCALE", None) or getattr(mod, "PR", None)

    if not isinstance(hp, dict) or not isinstance(pr, dict):
        raise ImportError(
            "core.scales must define dict scales: HP_SCALE/PR_SCALE (preferred) or HP/PR (fallback)."
        )

    hp_id = getattr(mod, "HP_ID", None)
    pr_id = getattr(mod, "PR_ID", None)
    return hp, pr, hp_id, pr_id


def _pairwise_verbose_wide_csv(
    *,
    metric: str,  # "hp" or "pr"
    positions: list[int],
    aligned_seq_names: list[str],
    aligned_seq_strings: list[str],
    pairwise: dict[str, list[float | None]],
    scale: dict[str, float],
) -> str:
    """
    Wide format, exactly one row per position:

    position,
    aa_<seq1>, score_<seq1>, aa_<seq2>, score_<seq2>, ...,
    abs_delta_<seqA>_<seqB>, abs_delta_<seqC>_<seqD>, ...

    Notes:
    - aa_* is the aligned symbol (AA or '-') at that position.
    - score_* is the normalized scale value for that symbol; gaps are treated as 0.0.
    - abs_delta_* comes from computed pairwise deltas (already absolute and normalized).
    """
    L = len(positions)
    nseq = min(len(aligned_seq_names), len(aligned_seq_strings))

    seq_slugs = [_slug(nm) for nm in aligned_seq_names[:nseq]]

    # Stable pair column order:
    # - prefer alignment order, then lexical.
    seq_index = {name: i for i, name in enumerate(aligned_seq_names[:nseq])}

    def pair_sort_key(k: str) -> tuple[int, int, str, str]:
        a, b = _split_pair_key(k)
        ia = seq_index.get(a, 10_000)
        ib = seq_index.get(b, 10_000)
        return (min(ia, ib), max(ia, ib), a, b)

    pair_keys = sorted(pairwise.keys(), key=pair_sort_key)
    pair_cols: list[tuple[str, str, str]] = []
    for k in pair_keys:
        a, b = _split_pair_key(k)
        col = f"abs_delta_{_slug(a)}_{_slug(b)}"
        pair_cols.append((k, a, b))

    # Build header
    fieldnames: list[str] = ["position"]
    for nm_slug in seq_slugs:
        fieldnames.append(f"aa_{nm_slug}")
        fieldnames.append(f"score_{nm_slug}")
    for k, a, b in pair_cols:
        fieldnames.append(f"abs_delta_{_slug(a)}_{_slug(b)}")

    # Write rows
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()

    for i in range(L):
        row: dict[str, Any] = {"position": positions[i]}

        # per-sequence values at this position
        for si in range(nseq):
            nm_slug = seq_slugs[si]
            s = aligned_seq_strings[si]
            sym = _norm_sym(s[i]) if i < len(s) else "-"
            row[f"aa_{nm_slug}"] = sym

            # gap treated as 0
            if sym == "-":
                row[f"score_{nm_slug}"] = 0.0
            else:
                v = scale.get(sym)
                row[f"score_{nm_slug}"] = "" if v is None else float(v)

        # per-pair deltas at this position
        for k, a, b in pair_cols:
            ys = pairwise.get(k, [])
            v = ys[i] if i < len(ys) else None
            row[f"abs_delta_{_slug(a)}_{_slug(b)}"] = "" if v is None else float(v)

        w.writerow(row)

    return buf.getvalue()


def _summary_rows(
    *,
    positions: list[int],
    median: list[float | None],
    p25: list[float | None],
    p75: list[float | None],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = min(len(positions), len(median), len(p25), len(p75))
    for i in range(n):
        rows.append(
            {
                "position": positions[i],
                "median_abs_delta": None if median[i] is None else float(median[i]),
                "p25_abs_delta": None if p25[i] is None else float(p25[i]),
                "p75_abs_delta": None if p75[i] is None else float(p75[i]),
            }
        )
    return rows


def _aa_freq_wide_csv(
    *,
    positions: list[int],
    composition_fraction: dict[str, list[float]],
) -> str:
    """
    Wide format:
    position, A, C, ... Y, -
    One row per position.
    Missing symbols are filled with 0.0.
    """
    fieldnames = ["position", *AA20, GAP]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()

    L = len(positions)
    for i in range(L):
        row: dict[str, Any] = {"position": positions[i]}
        for aa in AA20:
            ys = composition_fraction.get(aa, [])
            row[aa] = float(ys[i]) if i < len(ys) else 0.0
        ys_gap = composition_fraction.get(GAP, [])
        row[GAP] = float(ys_gap[i]) if i < len(ys_gap) else 0.0
        w.writerow(row)

    return buf.getvalue()


def build_export_zip_bytes(run: Any) -> bytes:
    created_at = _utc_now_iso()
    run_id = getattr(run, "run_id", "unknown")

    events_any = getattr(run, "events", None)
    events: list[Any] = events_any if isinstance(events_any, list) else []

    # inputs.fasta (optional)
    inputs_fasta = ""
    input_set = getattr(run, "input_set", None)
    if input_set is not None:
        entries = getattr(input_set, "entries", None)
        if isinstance(entries, list):
            recs: list[tuple[str, str]] = []
            for e in entries:
                name = getattr(e, "name", None) or getattr(e, "entry_id", "input")
                seq = getattr(e, "sequence", None)
                if isinstance(seq, str) and seq.strip():
                    recs.append((str(name), seq.strip()))
            if recs:
                inputs_fasta = _to_fasta(recs)

    # alignment.fasta + aligned sequences for verbose CSV
    alignment_fasta = ""
    aligned_names: list[str] = []
    aligned_strings: list[str] = []

    ar = getattr(run, "alignment_result", None)
    if ar is not None:
        seqs = getattr(ar, "sequences", None)
        if isinstance(seqs, list) and seqs:
            recs = []
            for s in seqs:
                name = getattr(s, "name", None) or getattr(s, "seq_id", "aligned")
                aligned_seq = getattr(s, "aligned_sequence", "")
                aligned_names.append(str(name))
                aligned_strings.append(str(aligned_seq))
                recs.append((str(name), str(aligned_seq)))
            alignment_fasta = _to_fasta(recs)

    p = getattr(run, "computed_profiles", None)
    if p is None:
        raise ValueError("computed_profiles missing; cannot export.")

    # positions (support both legacy and current naming)
    positions = getattr(p, "positions_1based", None)
    if not isinstance(positions, list) or not positions:
        positions = getattr(p, "aa_position", None)
    if not isinstance(positions, list) or not positions:
        raise ValueError("computed_profiles.positions_1based/aa_position missing/empty; cannot export.")

    # Load scales (for per-sequence score columns in verbose CSV)
    hp_scale, pr_scale, hp_id_fallback, pr_id_fallback = _load_scales()

    # HP
    hp_pairwise = getattr(p, "hp_pairwise_delta", {}) or {}
    hp_median = getattr(p, "hp_delta_median", []) or []
    hp_p25 = getattr(p, "hp_delta_p25", []) or []
    hp_p75 = getattr(p, "hp_delta_p75", []) or []
    hp_scale_id = getattr(p, "hp_scale_id", None) or hp_id_fallback

    hp_verbose_csv = _pairwise_verbose_wide_csv(
        metric="hp",
        positions=positions,
        aligned_seq_names=aligned_names,
        aligned_seq_strings=aligned_strings,
        pairwise=hp_pairwise,
        scale=hp_scale,
    )
    hp_sum_rows = _summary_rows(positions=positions, median=hp_median, p25=hp_p25, p75=hp_p75)

    # PR
    pr_pairwise = getattr(p, "pr_pairwise_delta", {}) or {}
    pr_median = getattr(p, "pr_delta_median", []) or []
    pr_p25 = getattr(p, "pr_delta_p25", []) or []
    pr_p75 = getattr(p, "pr_delta_p75", []) or []
    pr_scale_id = getattr(p, "pr_scale_id", None) or pr_id_fallback

    pr_verbose_csv = _pairwise_verbose_wide_csv(
        metric="pr",
        positions=positions,
        aligned_seq_names=aligned_names,
        aligned_seq_strings=aligned_strings,
        pairwise=pr_pairwise,
        scale=pr_scale,
    )
    pr_sum_rows = _summary_rows(positions=positions, median=pr_median, p25=pr_p25, p75=pr_p75)

    # composition wide CSV
    comp = getattr(p, "composition_fraction", None)
    if not isinstance(comp, dict):
        raise ValueError("computed_profiles.composition_fraction missing; cannot export.")
    aa_wide_csv = _aa_freq_wide_csv(positions=positions, composition_fraction=comp)

    # serialize summaries
    hp_sum_csv = _write_csv(hp_sum_rows, ["position", "median_abs_delta", "p25_abs_delta", "p75_abs_delta"])
    pr_sum_csv = _write_csv(pr_sum_rows, ["position", "median_abs_delta", "p25_abs_delta", "p75_abs_delta"])
    provenance_jsonl = _jsonl(events)

    tool: dict[str, Any] = {}
    if ar is not None:
        ex = getattr(ar, "execution", None)
        if ex is not None:
            tool = {
                "tool_name": getattr(ex, "tool_name", None),
                "tool_version": getattr(ex, "tool_version", None),
                "command": getattr(ex, "command", None),
                "return_code": getattr(ex, "return_code", None),
                "duration_seconds": getattr(ex, "duration_seconds", None),
            }

    manifest = {
        "created_at": created_at,
        "run_id": run_id,
        "scales": {"hp_scale_id": hp_scale_id, "pr_scale_id": pr_scale_id},
        "alignment_tool": tool,
        "files": [
            {"path": "manifest.json", "kind": "metadata"},
            {"path": "provenance.jsonl", "kind": "provenance"},
            {"path": "inputs.fasta", "kind": "inputs", "optional": True},
            {"path": "alignment.fasta", "kind": "alignment"},
            {"path": "hp_pairwise_verbose.csv", "kind": "data"},
            {"path": "hp_summary.csv", "kind": "data"},
            {"path": "pr_pairwise_verbose.csv", "kind": "data"},
            {"path": "pr_summary.csv", "kind": "data"},
            {"path": "aa_freq_per_position.csv", "kind": "data"},
        ],
        "notes": "All files were generated in-memory for this run.",
    }
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", manifest_json)
        zf.writestr("provenance.jsonl", provenance_jsonl)
        if inputs_fasta:
            zf.writestr("inputs.fasta", inputs_fasta)
        zf.writestr("alignment.fasta", alignment_fasta)

        zf.writestr("hp_pairwise_verbose.csv", hp_verbose_csv)
        zf.writestr("hp_summary.csv", hp_sum_csv)
        zf.writestr("pr_pairwise_verbose.csv", pr_verbose_csv)
        zf.writestr("pr_summary.csv", pr_sum_csv)
        zf.writestr("aa_freq_per_position.csv", aa_wide_csv)

    return zip_buf.getvalue()
