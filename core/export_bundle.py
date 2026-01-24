# core/export_bundle.py
from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any, Iterable


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


def _pairwise_long_rows(
    *,
    metric: str,  # "hp" or "pr"
    position: list[int],
    pairwise: dict[str, list[float | None]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, ys in pairwise.items():
        a, b = _split_pair_key(key)
        n = min(len(position), len(ys))
        for i in range(n):
            v = ys[i]
            if v is None:
                continue
            rows.append(
                {
                    "metric": metric,
                    "position": position[i],
                    "seq_a": a,
                    "seq_b": b,
                    "abs_delta": float(v),
                }
            )
    return rows


def _summary_rows(
    *,
    metric: str,
    position: list[int],
    median: list[float | None],
    p25: list[float | None],
    p75: list[float | None],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = min(len(position), len(median), len(p25), len(p75))
    for i in range(n):
        rows.append(
            {
                "metric": metric,
                "col_1based": position[i],
                "median_abs_delta": None if median[i] is None else float(median[i]),
                "p25_abs_delta": None if p25[i] is None else float(p25[i]),
                "p75_abs_delta": None if p75[i] is None else float(p75[i]),
            }
        )
    return rows


def _aa_freq_wide_csv(
    *,
    position: list[int],
    composition_fraction: dict[str, list[float]],
) -> str:
    """
    Wide format:
    col_1based, A, C, ... Y, -
    One row per position.
    Missing symbols are filled with 0.0.
    """
    fieldnames = ["col_1based", *AA20, GAP]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()

    L = len(position)
    # Ensure we can index safely
    for i in range(L):
        row: dict[str, Any] = {"col_1based": position[i]}
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

    # alignment.fasta
    alignment_fasta = ""
    ar = getattr(run, "alignment_result", None)
    if ar is not None:
        seqs = getattr(ar, "sequences", None)
        if isinstance(seqs, list) and seqs:
            recs = []
            for s in seqs:
                name = getattr(s, "name", None) or getattr(s, "seq_id", "aligned")
                aligned_seq = getattr(s, "aligned_sequence", "")
                recs.append((str(name), str(aligned_seq)))
            alignment_fasta = _to_fasta(recs)

    p = getattr(run, "computed_profiles", None)
    if p is None:
        raise ValueError("computed_profiles missing; cannot export.")

    positions = getattr(p, "position", None)
    if not isinstance(positions, list) or not positions:
        raise ValueError("computed_profiles.position missing/empty; cannot export.")

    # HP
    hp_pairwise = getattr(p, "hp_pairwise_delta", {}) or {}
    hp_median = getattr(p, "hp_delta_median", []) or []
    hp_p25 = getattr(p, "hp_delta_p25", []) or []
    hp_p75 = getattr(p, "hp_delta_p75", []) or []
    hp_scale_id = getattr(p, "hp_scale_id", None)

    hp_pair_rows = _pairwise_long_rows(metric="hp", position=positions, pairwise=hp_pairwise)
    hp_sum_rows = _summary_rows(metric="hp", position=positions, median=hp_median, p25=hp_p25, p75=hp_p75)

    # PR
    pr_pairwise = getattr(p, "pr_pairwise_delta", {}) or {}
    pr_median = getattr(p, "pr_delta_median", []) or []
    pr_p25 = getattr(p, "pr_delta_p25", []) or []
    pr_p75 = getattr(p, "pr_delta_p75", []) or []
    pr_scale_id = getattr(p, "pr_scale_id", None)

    pr_pair_rows = _pairwise_long_rows(metric="pr", position=positions, pairwise=pr_pairwise)
    pr_sum_rows = _summary_rows(metric="pr", position=positions, median=pr_median, p25=pr_p25, p75=pr_p75)

    # composition wide CSV
    comp = getattr(p, "composition_fraction", None)
    if not isinstance(comp, dict):
        raise ValueError("computed_profiles.composition_fraction missing; cannot export.")
    aa_wide_csv = _aa_freq_wide_csv(position=positions, composition_fraction=comp)

    # serialize
    hp_pair_csv = _write_csv(hp_pair_rows, ["metric", "col_1based", "seq_a", "seq_b", "abs_delta"])
    pr_pair_csv = _write_csv(pr_pair_rows, ["metric", "col_1based", "seq_a", "seq_b", "abs_delta"])
    hp_sum_csv = _write_csv(hp_sum_rows, ["metric", "col_1based", "median_abs_delta", "p25_abs_delta", "p75_abs_delta"])
    pr_sum_csv = _write_csv(pr_sum_rows, ["metric", "col_1based", "median_abs_delta", "p25_abs_delta", "p75_abs_delta"])
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
            {"path": "hp_pairwise_long.csv", "kind": "data"},
            {"path": "hp_summary.csv", "kind": "data"},
            {"path": "pr_pairwise_long.csv", "kind": "data"},
            {"path": "pr_summary.csv", "kind": "data"},
            {"path": "aa_freq_per_position.csv", "kind": "data"},
        ],
        "notes": "All files were generated in-memory for this run. No persistence is intended.",
    }
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", manifest_json)
        zf.writestr("provenance.jsonl", provenance_jsonl)
        if inputs_fasta:
            zf.writestr("inputs.fasta", inputs_fasta)
        zf.writestr("alignment.fasta", alignment_fasta)

        zf.writestr("hp_pairwise_long.csv", hp_pair_csv)
        zf.writestr("hp_summary.csv", hp_sum_csv)
        zf.writestr("pr_pairwise_long.csv", pr_pair_csv)
        zf.writestr("pr_summary.csv", pr_sum_csv)
        zf.writestr("aa_freq_per_position.csv", aa_wide_csv)

    return zip_buf.getvalue()
