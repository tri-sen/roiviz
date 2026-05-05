from __future__ import annotations

import plotly.graph_objects as go

from core.analysis_session_models import ComputedProfiles
from core.constants import (
    AMINO_ACID_COLOR_PALETTES,
    DEFAULT_AMINO_ACID_COLOR_PALETTE,
    GAP_CHAR,
    STANDARD_AMINO_ACIDS,
)

_FALLBACK_COLOR = "#888888"
_ALL_SYMBOLS: list[str] = list(STANDARD_AMINO_ACIDS) + [GAP_CHAR]


def _resolve_palette(palette: dict[str, str] | None) -> dict[str, str]:
    if palette is not None:
        return palette
    return AMINO_ACID_COLOR_PALETTES[DEFAULT_AMINO_ACID_COLOR_PALETTE]


def _build_comp_by_pos(profiles: ComputedProfiles) -> dict[int, dict[str, float]]:
    """Build position → {symbol → fraction} from the flat composition list."""
    comp: dict[int, dict[str, float]] = {}
    for entry in profiles.position_composition:
        comp.setdefault(entry.position, {})[entry.symbol] = entry.fraction
    return comp


def _build_position_hover(
    profiles: ComputedProfiles,
    comp_by_pos: dict[int, dict[str, float]],
    n_seqs: int,
) -> dict[int, str]:
    hover: dict[int, str] = {}
    for pos in range(1, profiles.alignment_length + 1):
        composition = comp_by_pos.get(pos, {})
        sorted_items = sorted(
            composition.items(), key=lambda x: x[1], reverse=True
        )
        lines = [
            f"<b>Position {pos}</b>",
            f"Sequences: {n_seqs}",
        ]
        for sym, frac in sorted_items:
            if frac > 0:
                count = round(frac * n_seqs)
                lines.append(f"{sym}: {frac:.1%} ({count})")
        hover[pos] = "<br>".join(lines)
    return hover


def build_composition_stacked_columns(
    profiles: ComputedProfiles,
    palette: dict[str, str] | None = None,
) -> go.Figure:
    resolved = _resolve_palette(palette)
    positions = list(range(1, profiles.alignment_length + 1))
    n_seqs = len(profiles.aligned_sequence_ids)
    comp_by_pos = _build_comp_by_pos(profiles)
    position_hover = _build_position_hover(profiles, comp_by_pos, n_seqs)

    fig = go.Figure()

    for sym in _ALL_SYMBOLS:
        fracs = [comp_by_pos.get(pos, {}).get(sym, 0.0) for pos in positions]
        hover_texts = [position_hover.get(pos, "") for pos in positions]

        color = resolved.get(sym, _FALLBACK_COLOR)
        opacity = 0.5 if sym == GAP_CHAR else 1.0
        name = "Gap (-)" if sym == GAP_CHAR else sym

        fig.add_trace(
            go.Bar(
                x=positions,
                y=fracs,
                name=name,
                marker=dict(color=color, opacity=opacity),
                customdata=hover_texts,
                hovertemplate="%{customdata}<extra></extra>",
            )
        )

    fig.update_layout(
        title="Alignment Composition",
        barmode="stack",
        xaxis=dict(title="Aligned position", tickformat=".0f"),
        yaxis=dict(title="Frequency", range=[0, 1.0], tickformat=".0%", fixedrange=True),
        hovermode="closest",
        margin=dict(l=60, r=20, t=60, b=50),
        legend=dict(title="Symbol"),
    )

    return fig


_TIE_Y_OFFSET = 0.01


def build_composition_letter_symbols(
    profiles: ComputedProfiles,
    palette: dict[str, str] | None = None,
) -> go.Figure:
    resolved = _resolve_palette(palette)
    n_seqs = len(profiles.aligned_sequence_ids)
    comp_by_pos = _build_comp_by_pos(profiles)
    position_hover = _build_position_hover(profiles, comp_by_pos, n_seqs)

    symbol_x: dict[str, list[int]] = {sym: [] for sym in _ALL_SYMBOLS}
    symbol_visual_y: dict[str, list[float]] = {sym: [] for sym in _ALL_SYMBOLS}
    symbol_raw_y: dict[str, list[float]] = {sym: [] for sym in _ALL_SYMBOLS}
    symbol_hover: dict[str, list[str]] = {sym: [] for sym in _ALL_SYMBOLS}

    for pos in range(1, profiles.alignment_length + 1):
        composition = comp_by_pos.get(pos, {})
        freq_tally: dict[float, int] = {}
        for sym in _ALL_SYMBOLS:
            frac = composition.get(sym, 0.0)
            if frac <= 0:
                continue
            nth = freq_tally.get(frac, 0)
            freq_tally[frac] = nth + 1
            symbol_x[sym].append(pos)
            symbol_visual_y[sym].append(frac + nth * _TIE_Y_OFFSET)
            symbol_raw_y[sym].append(frac)
            symbol_hover[sym].append(position_hover.get(pos, ""))

    fig = go.Figure()

    for sym in _ALL_SYMBOLS:
        if not symbol_x[sym]:
            continue

        color = resolved.get(sym, _FALLBACK_COLOR)
        name = "Gap (-)" if sym == GAP_CHAR else sym

        fig.add_trace(
            go.Scatter(
                x=symbol_x[sym],
                y=symbol_visual_y[sym],
                mode="text",
                text=[sym] * len(symbol_x[sym]),
                textfont=dict(color=color, size=14),
                name=name,
                customdata=[[r] for r in symbol_raw_y[sym]],
                hovertext=symbol_hover[sym],
                hovertemplate="%{hovertext}<extra></extra>",
                showlegend=True,
            )
        )

    fig.update_layout(
        title="Alignment Composition (letter/gap symbols)",
        xaxis=dict(title="Aligned position", tickformat=".0f"),
        yaxis=dict(
            title="Frequency",
            range=[-0.05, 1.05],
            fixedrange=True,
            showticklabels=False,
        ),
        hovermode="closest",
        margin=dict(l=60, r=20, t=80, b=50),
        legend=dict(title="Symbol"),
    )

    return fig
