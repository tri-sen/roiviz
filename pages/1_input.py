"""
Input page (UI-only, Step 3).

Rules:
- UI-only rendering; no subprocess/HTTP/filesystem writes.
- Uses core validation (pure) and pipeline.commit_inputs (pure orchestration, no side effects).
- Draft inputs live in st.session_state (UI-owned).
- Committed inputs live in run.input_set (core-owned).
"""

from __future__ import annotations

import streamlit as st

from core.run_factory import create_new_run
from ui.sidebar import render_sidebar
from core.pipeline import PipelineError, commit_inputs
from core.validation import validate_aa_sequence, validate_name


def _get_run():
    return st.session_state.get("run")


def _get_draft() -> list[dict[str, str]]:
    if "draft_inputs" not in st.session_state:
        st.session_state["draft_inputs"] = [
            {"name": "seq1", "sequence": ""},
            {"name": "seq2", "sequence": ""},
        ]
    return st.session_state["draft_inputs"]


def _add_draft_row() -> None:
    draft = _get_draft()
    if len(draft) < 10:
        draft.append({"name": f"seq{len(draft)+1}", "sequence": ""})


def _remove_draft_row(idx: int) -> None:
    draft = _get_draft()
    if len(draft) > 2 and 0 <= idx < len(draft):
        draft.pop(idx)


st.title("Step 1 — Input (manual AA)")

run = _get_run()
if run is None:
    st.error("RunState is missing. Go to the main page (app.py) to initialize a run.")
    st.stop()

render_sidebar(create_new_run)

st.subheader("Run status")
st.json(
    {
        "run_id": run.run_id,
        "phase": run.phase.value,
        "event_count": len(run.events),
        "inputs_committed": run.input_set is not None,
    }
)

# If inputs already committed: show summary and stop editing
if run.input_set is not None:
    st.success("Inputs are committed for this run (read-only). Start a New run to change inputs.")
    st.write("Committed entries:")
    st.dataframe(
        [{"name": e.name, "length": len(e.aa_sequence), "source": e.source.value} for e in run.input_set.entries],
        use_container_width=True,
    )
    st.stop()

st.divider()
st.subheader("Draft inputs")

draft = _get_draft()

col_a, col_b = st.columns([1, 1], vertical_alignment="center")
with col_a:
    st.button("Add entry", on_click=_add_draft_row, disabled=(len(draft) >= 10))
with col_b:
    st.caption("Minimum 2, maximum 10 entries. No FASTA parsing yet (manual AA only).")

all_valid = True
valid_count = 0
validation_messages: list[str] = []

for idx, item in enumerate(draft):
    with st.container(border=True):
        top = st.columns([3, 1])
        with top[0]:
            st.write(f"Entry {idx+1}")
        with top[1]:
            st.button("Remove", key=f"rm_{idx}", on_click=_remove_draft_row, args=(idx,), disabled=(len(draft) <= 2))

        name = st.text_input("Name", value=item.get("name", ""), key=f"name_{idx}")
        seq = st.text_area("AA sequence", value=item.get("sequence", ""), key=f"seq_{idx}", height=120)

        # write back to draft (UI-owned)
        item["name"] = name
        item["sequence"] = seq

        name_res = validate_name(name)
        seq_res = validate_aa_sequence(seq)

        entry_ok = name_res.ok and seq_res.ok
        if entry_ok:
            valid_count += 1
            st.success(f"Valid — length: {len(seq_res.normalized)} aa")
        else:
            all_valid = False
            if not name_res.ok:
                st.error(name_res.error)
                validation_messages.append(f"Entry {idx+1}: {name_res.error}")
            if not seq_res.ok:
                st.error(seq_res.error)
                validation_messages.append(f"Entry {idx+1}: {seq_res.error}")

st.divider()
st.subheader("Commit")

can_commit = (valid_count >= 2) and all_valid

if not can_commit:
    st.warning(
        "Commit is disabled until all entries are valid and at least 2 sequences are provided.\n"
        f"Valid entries: {valid_count} / {len(draft)}"
    )

if st.button("Commit inputs (Next)", type="primary", disabled=not can_commit):
    try:
        commit_inputs(run=run, draft_items=draft)
        st.success("Inputs committed. Phase advanced to ALIGNMENT.")
        st.rerun()
    except PipelineError as e:
        st.error(str(e))
