from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

import streamlit as st

from core.analysis_session_models import SourceType
from core.input.parsers import parse_fasta_file, parse_genbank, parse_genbank_file
from core.input.service import (
    ImportedCandidateRecord,
    ImportedSourceRecord,
    SelectedSequenceRecord,
    commit_input,
    validate_sequence,
)
from core.state import (
    clear_alignment_and_analysis,
    clear_feedback,
    get_feedback,
    get_session,
    has_computed_profiles,
    has_valid_alignment,
    has_valid_input,
    mark_session_changed,
    set_feedback,
)
from integrations.ncbi import fetch_genbank_text
from components import render_pipeline_navigator, render_processing_history_expander, render_workflow_box

_MIN = 2
_MAX = 6
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _new_draft_id() -> str:
    return uuid.uuid4().hex[:8]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _wrap_sequence(seq: str, width: int = 60) -> str:
    return "\n".join(seq[i : i + width] for i in range(0, len(seq), width))


# ── draft state helpers ───────────────────────────────────────────────────────


def _init_editing_fresh() -> None:
    st.session_state["ui_input_selected_seqs"] = []
    st.session_state["ui_input_sources"] = []


def _init_editing_from_committed(session: object) -> None:
    # Build a lookup of candidates by source_id from the flat candidates list.
    cands_by_src: dict[str, list] = {}
    for cand in session.input_stage.candidates:
        cands_by_src.setdefault(cand.source_id, []).append(cand)

    sources = []
    for src in session.input_stage.sources:
        if src.source_type == SourceType.MANUAL:
            continue
        sources.append(
            {
                "source_id": src.id,
                "filename": src.filename,
                "source_type": str(src.source_type),
                "accession": src.accession,
                "imported_at": src.imported_at,
                "candidates": [
                    {
                        "cand_id": c.id,
                        "name": c.name,
                        "sequence": c.sequence,
                        "description": c.description,
                        "feature_type": c.feature_type,
                        "feature_location": c.feature_location,
                    }
                    for c in cands_by_src.get(src.id, [])
                ],
            }
        )
    st.session_state["ui_input_sources"] = sources

    source_by_id = {src.id: src for src in session.input_stage.sources}

    seqs = []
    for seq in session.input_stage.selected_sequences:
        draft_id = _new_draft_id()
        src = source_by_id.get(seq.source_id)
        if src and src.source_type != SourceType.MANUAL:
            seqs.append(
                {
                    "draft_id": draft_id,
                    "name": seq.name,
                    "sequence": seq.sequence,
                    "imported": True,
                    "imported_source_id": seq.source_id,
                    "imported_cand_id": seq.candidate_id,
                    "imported_cand_original_name": seq.name,
                }
            )
        else:
            seqs.append({"draft_id": draft_id, "name": seq.name, "sequence": seq.sequence})

    st.session_state["ui_input_selected_seqs"] = seqs


def _clear_editing_state() -> None:
    st.session_state.pop("ui_input_selected_seqs", None)
    st.session_state.pop("ui_input_sources", None)
    st.session_state.pop("ui_manual_input_v", None)
    st.session_state.pop("ui_input_preview_cand_id", None)
    st.session_state.pop("ui_input_preview_source_id", None)


# ── source / candidate helpers ────────────────────────────────────────────────


def _is_candidate_added(source_id: str, cand_id: str) -> bool:
    for slot in st.session_state.get("ui_input_selected_seqs", []):
        if (
            slot.get("imported")
            and slot.get("imported_source_id") == source_id
            and slot.get("imported_cand_id") == cand_id
        ):
            return True
    return False


def _add_candidate_to_selected(
    source_id: str, cand: dict, selected_seqs: list[dict]
) -> None:
    draft_id = _new_draft_id()
    selected_seqs.append(
        {
            "draft_id": draft_id,
            "name": cand["name"],
            "sequence": cand["sequence"],
            "imported": True,
            "imported_source_id": source_id,
            "imported_cand_id": cand["cand_id"],
            "imported_cand_original_name": cand["name"],
        }
    )


def _delete_source(source_id: str) -> None:
    selected_seqs = st.session_state.get("ui_input_selected_seqs", [])
    st.session_state["ui_input_selected_seqs"] = [
        s
        for s in selected_seqs
        if not (s.get("imported") and s.get("imported_source_id") == source_id)
    ]
    sources = st.session_state.get("ui_input_sources", [])
    st.session_state["ui_input_sources"] = [
        s for s in sources if s["source_id"] != source_id
    ]


# ── dialogs ───────────────────────────────────────────────────────────────────


@st.dialog("Reopen input stage?", dismissible=False, icon=":material/warning:")
def _dialog_reopen_input() -> None:
    st.warning(
        "Reopening input will delete all downstream results "
        "(alignment and analysis). This cannot be undone inside the app."
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancel"):
            st.session_state["ui_input_show_reopen_confirm"] = False
            st.rerun()
    with c2:
        if st.button("Delete downstream data and reopen", type="primary"):
            _session = get_session()
            clear_alignment_and_analysis(_session)
            _clear_editing_state()
            _init_editing_from_committed(_session)
            st.session_state["ui_input_editing"] = True
            st.session_state["ui_input_show_reopen_confirm"] = False
            set_feedback("info", "Input reopened. Alignment and analysis have been cleared.")
            st.rerun()


# ── tab renderers ─────────────────────────────────────────────────────────────


def _render_manual_tab(selected_seqs: list[dict]) -> None:
    st.caption(
        "Enter a sequence name and amino acid sequence "
        "(A C D E F G H I K L M N P Q R S T V W Y). "
        "Click Add to append it to the list below."
    )
    _v = st.session_state.get("ui_manual_input_v", 0)
    col1, col2 = st.columns([1, 1])
    with col1:
        manual_name = st.text_input("Name", key=f"ui_mn_{_v}")
    with col2:
        manual_seq = st.text_area("Sequence (amino acids)", key=f"ui_ms_{_v}", height=100)
    if st.button("Add sequence", key=f"ui_ma_{_v}"):
        ok, err = validate_sequence(manual_name, manual_seq)
        if not ok:
            st.error(err)
        else:
            existing_names = {d.get("name", "").strip() for d in selected_seqs}
            if manual_name.strip() in existing_names:
                st.error(
                    f"A sequence named '{manual_name.strip()}' is already in the list."
                )
            else:
                draft_id = _new_draft_id()
                selected_seqs.append(
                    {
                        "draft_id": draft_id,
                        "name": manual_name.strip(),
                        "sequence": manual_seq.strip().upper(),
                    }
                )
                st.session_state["ui_manual_input_v"] = _v + 1
                st.rerun()


def _render_fasta_tab() -> None:
    st.caption(
        "Upload a protein FASTA file. Each record must contain only the "
        "20 standard amino acids. Nucleotide sequences are rejected."
    )
    v = st.session_state.get("ui_fasta_upload_v", 0)
    uploaded = st.file_uploader(
        "Protein FASTA file",
        type=["fasta", "fa", "faa", "txt"],
        key=f"ui_fasta_uploader_{v}",
    )
    if uploaded is None:
        return

    candidates, err = parse_fasta_file(uploaded.name, uploaded.read())
    if err:
        st.error(err)
        return

    source_id = f"ts_{uuid.uuid4().hex[:8]}"
    st.session_state.setdefault("ui_input_sources", []).append(
        {
            "source_id": source_id,
            "filename": uploaded.name,
            "source_type": str(SourceType.FASTA_UPLOAD),
            "accession": None,
            "imported_at": None,
            "candidates": [
                {
                    "cand_id": c.cand_id,
                    "name": c.name,
                    "sequence": c.sequence,
                    "description": c.description,
                    "feature_type": c.feature_type,
                    "feature_location": c.feature_location,
                }
                for c in candidates
            ],
        }
    )
    st.session_state["ui_fasta_upload_v"] = v + 1
    st.rerun()


def _render_genbank_tab() -> None:
    st.caption(
        "Upload a GenBank file. mat_peptide features are extracted as protein "
        "candidates. Files without usable mat_peptide translations are rejected."
    )
    v = st.session_state.get("ui_gb_upload_v", 0)
    uploaded = st.file_uploader(
        "GenBank file",
        type=["gb", "gbk", "genbank", "txt"],
        key=f"ui_gb_uploader_{v}",
    )
    if uploaded is None:
        return

    candidates, err = parse_genbank_file(uploaded.name, uploaded.read())
    if err:
        st.error(err)
        return

    source_id = f"ts_{uuid.uuid4().hex[:8]}"
    st.session_state.setdefault("ui_input_sources", []).append(
        {
            "source_id": source_id,
            "filename": uploaded.name,
            "source_type": str(SourceType.GENBANK_UPLOAD),
            "accession": None,
            "imported_at": None,
            "candidates": [
                {
                    "cand_id": c.cand_id,
                    "name": c.name,
                    "sequence": c.sequence,
                    "description": c.description,
                    "feature_type": c.feature_type,
                    "feature_location": c.feature_location,
                }
                for c in candidates
            ],
        }
    )
    st.session_state["ui_gb_upload_v"] = v + 1
    st.rerun()


def _render_ncbi_tab() -> None:
    st.caption(
        "Fetch a GenBank record from NCBI nuccore by accession ID. "
        "mat_peptide features are extracted as protein candidates."
    )
    email = st.text_input(
        "Email (required for NCBI)",
        placeholder="your.email@example.com",
        key="ui_ncbi_email",
    )
    accession = st.text_input(
        "Accession ID", placeholder="NC_001802", key="ui_ncbi_accession"
    )
    if st.button("Fetch", key="ui_ncbi_fetch_btn"):
        if not email or not accession:
            st.error("Email and accession are required.")
        elif not _EMAIL_RE.match(email.strip()):
            st.error("Email does not look valid. NCBI requires a real email address.")
        else:
            with st.spinner("Fetching from NCBI…"):
                try:
                    raw_text = fetch_genbank_text(accession.strip(), email.strip())
                    candidates, err = parse_genbank(raw_text)
                    if err:
                        st.error(err)
                    else:
                        source_id = f"ts_ncbi_{uuid.uuid4().hex[:8]}"
                        st.session_state.setdefault("ui_input_sources", []).append(
                            {
                                "source_id": source_id,
                                "filename": None,
                                "source_type": str(SourceType.NCBI_FETCH),
                                "accession": accession.strip(),
                                "imported_at": _utc_now(),
                                "candidates": [
                                    {
                                        "cand_id": c.cand_id,
                                        "name": c.name,
                                        "sequence": c.sequence,
                                        "description": c.description,
                                        "feature_type": c.feature_type,
                                        "feature_location": c.feature_location,
                                    }
                                    for c in candidates
                                ],
                            }
                        )
                        st.rerun()
                except Exception as exc:
                    st.error(f"NCBI fetch failed: {exc}")


# ── sources section ───────────────────────────────────────────────────────────


def _fmt_timestamp(ts: str) -> str:
    return ts[:16].replace("T", " ") + " UTC"


def _render_sources(selected_seqs: list[dict]) -> None:
    sources: list[dict] = st.session_state.get("ui_input_sources", [])
    if not sources:
        return

    st.subheader("Sources")

    preview_cand_id = st.session_state.get("ui_input_preview_cand_id")
    preview_source_id = st.session_state.get("ui_input_preview_source_id")

    for src in sources:
        source_id = src["source_id"]
        st_val = src["source_type"]
        candidates: list[dict] = src["candidates"]

        with st.container(border=True):
            # ── source header ─────────────────────────────────────────────────
            col_type, col_ident, col_ts, col_remove = st.columns([1, 2, 3, 1])
            with col_type:
                if st_val == str(SourceType.NCBI_FETCH):
                    st.write("**NCBI**")
                elif st_val == str(SourceType.FASTA_UPLOAD):
                    st.write("**FASTA**")
                else:
                    st.write("**GenBank**")
            with col_ident:
                if st_val == str(SourceType.NCBI_FETCH):
                    st.write(src.get("accession") or "—")
                else:
                    st.write(src.get("filename") or "—")
            with col_ts:
                imported_at = src.get("imported_at")
                if imported_at:
                    st.caption(f"imported {_fmt_timestamp(imported_at)}")
            with col_remove:
                if st.button("Remove", key=f"rm_src_{source_id}"):
                    _delete_source(source_id)
                    st.rerun()

            # ── column headers ────────────────────────────────────────────────
            if candidates:
                h1, h2, h3, _, _ = st.columns([4, 2, 1, 1, 1])
                with h1:
                    st.caption("Candidate")
                with h2:
                    st.caption("Note")
                with h3:
                    st.caption("Length")

            # ── candidate rows ────────────────────────────────────────────────
            for cand in candidates:
                cand_id = cand["cand_id"]
                already_added = _is_candidate_added(source_id, cand_id)
                is_previewed = (
                    preview_cand_id == cand_id and preview_source_id == source_id
                )

                c_name, c_note, c_len, c_prev, c_add = st.columns([4, 2, 1, 1, 1])
                with c_name:
                    marker = "▶ " if is_previewed else ""
                    name_text = f"**{marker}{cand['name']}**" if is_previewed else cand["name"]
                    st.write(name_text)
                with c_note:
                    note = cand.get("description") or ""
                    st.caption(note[:30] + ("…" if len(note) > 30 else ""))
                with c_len:
                    st.caption(f"{len(cand['sequence'])} aa")
                with c_prev:
                    if st.button("Preview", key=f"prev_{cand_id}"):
                        if is_previewed:
                            st.session_state.pop("ui_input_preview_cand_id", None)
                            st.session_state.pop("ui_input_preview_source_id", None)
                        else:
                            st.session_state["ui_input_preview_cand_id"] = cand_id
                            st.session_state["ui_input_preview_source_id"] = source_id
                        st.rerun()
                with c_add:
                    if already_added:
                        st.caption("Added")
                    else:
                        if st.button("Add", key=f"add_cand_{cand_id}", type="primary"):
                            _add_candidate_to_selected(source_id, cand, selected_seqs)
                            st.rerun()

            # ── preview panel ─────────────────────────────────────────────────
            if preview_source_id == source_id and preview_cand_id:
                preview_cand = next(
                    (c for c in candidates if c["cand_id"] == preview_cand_id), None
                )
                if preview_cand:
                    with st.container(border=True):
                        col_title, col_close = st.columns([5, 1])
                        with col_title:
                            st.write(
                                f"**Preview: {preview_cand['name']}** — "
                                f"{len(preview_cand['sequence'])} aa"
                            )
                        with col_close:
                            if st.button("Close preview", key=f"close_prev_{preview_cand_id}"):
                                st.session_state.pop("ui_input_preview_cand_id", None)
                                st.session_state.pop("ui_input_preview_source_id", None)
                                st.rerun()
                        st.code(_wrap_sequence(preview_cand["sequence"]), language=None)


# ── page ──────────────────────────────────────────────────────────────────────

if "session" not in st.session_state:
    st.error("No active session. Go to the home page to start one.")
    st.stop()

session = get_session()

st.title("Step 1: Input")
render_pipeline_navigator(session, "input")

feedback = get_feedback()
if feedback:
    _dispatch = {"success": st.success, "error": st.error, "warning": st.warning}
    _dispatch.get(feedback["type"], st.info)(feedback["message"])
    clear_feedback()

render_workflow_box(session, "input")

is_committed = has_valid_input(session)
has_downstream = has_valid_alignment(session) or has_computed_profiles(session)

if "ui_input_editing" not in st.session_state:
    st.session_state["ui_input_editing"] = not is_committed

# ── locked (read-only) view ───────────────────────────────────────────────────

if not st.session_state["ui_input_editing"]:
    st.subheader(f"Committed sequences ({len(session.input_stage.selected_sequences)})")
    for seq in session.input_stage.selected_sequences:
        with st.container(border=True):
            col_name, col_meta = st.columns([4, 1])
            with col_name:
                st.write(f"**{seq.name}**")
            with col_meta:
                st.caption(f"{len(seq.sequence)} aa")

    col_edit, _, col_nav = st.columns(3)
    with col_edit:
        if has_downstream:
            if st.button("Edit input again", type="secondary"):
                st.session_state["ui_input_show_reopen_confirm"] = True
            if st.session_state.get("ui_input_show_reopen_confirm"):
                _dialog_reopen_input()
        else:
            if st.button("Edit input", type="secondary"):
                _clear_editing_state()
                _init_editing_from_committed(session)
                st.session_state["ui_input_editing"] = True
                st.rerun()
    with col_nav:
        if st.button("Step 2: Alignment →", type="secondary", use_container_width=True):
            st.switch_page("pages/2_Alignment.py")

# ── editing view ──────────────────────────────────────────────────────────────

else:
    if "ui_input_selected_seqs" not in st.session_state:
        if is_committed:
            _init_editing_from_committed(session)
        else:
            _init_editing_fresh()

    selected_seqs: list[dict] = st.session_state["ui_input_selected_seqs"]

    # ── add sequences ─────────────────────────────────────────────────────────

    st.subheader("Add sequences")
    tab_manual, tab_fasta, tab_gb, tab_ncbi = st.tabs(
        ["Manual", "FASTA", "GenBank", "NCBI"]
    )
    with tab_manual:
        _render_manual_tab(selected_seqs)
    with tab_fasta:
        _render_fasta_tab()
    with tab_gb:
        _render_genbank_tab()
    with tab_ncbi:
        _render_ncbi_tab()

    # ── sources ───────────────────────────────────────────────────────────────

    _render_sources(selected_seqs)

    # ── selected sequences ────────────────────────────────────────────────────

    st.divider()
    st.subheader(f"Selected sequences ({len(selected_seqs)})")

    if not selected_seqs:
        st.info("No sequences added yet. Use the 'Add sequences' section above.")
    else:
        for i, slot in enumerate(selected_seqs):
            draft_id = slot["draft_id"]
            is_imported = slot.get("imported", False)
            seq = slot.get("sequence", "")
            source_label = "Imported" if is_imported else "Manual"
            with st.container(border=True):
                col_name, col_meta, col_remove = st.columns([4, 2, 1])
                with col_name:
                    edited_name = st.text_input(
                        "Name",
                        value=slot.get("name", ""),
                        key=f"sn_{draft_id}",
                        label_visibility="collapsed",
                    )
                    slot["name"] = edited_name
                with col_meta:
                    st.caption(f"{len(seq)} aa · {source_label}")
                with col_remove:
                    if st.button("Remove", key=f"rm_{draft_id}"):
                        selected_seqs.pop(i)
                        st.rerun()
                preview = seq[:60] + ("…" if len(seq) > 60 else "")
                st.code(preview, language=None)
                with st.expander("Full sequence"):
                    st.code(_wrap_sequence(seq), language=None)

    # ── validation summary ────────────────────────────────────────────────────

    st.divider()

    names = [d.get("name", "").strip() for d in selected_seqs]
    seqs_text = [d.get("sequence", "").strip() for d in selected_seqs]
    n_seq = len(selected_seqs)

    has_duplicates = n_seq > 0 and len(set(names)) < len(names)
    invalid_errors: list[str] = []
    for name, seq in zip(names, seqs_text):
        ok, err = validate_sequence(name, seq)
        if not ok:
            invalid_errors.append(f"'{name or '(unnamed)'}': {err}")
    has_invalid = bool(invalid_errors)
    too_many = n_seq > _MAX

    can_commit = _MIN <= n_seq <= _MAX and not has_duplicates and not has_invalid

    if can_commit:
        st.success("Input is ready for alignment.")
    elif n_seq == 0:
        st.info("Add at least 2 valid protein sequences to continue to alignment.")
    elif n_seq == 1 and not has_invalid:
        st.info("Add one more valid protein sequence to continue to alignment.")
    else:
        if n_seq < _MIN:
            st.info("Add at least 2 valid protein sequences to continue to alignment.")
        if too_many:
            st.warning(f"{n_seq} sequences selected — at most {_MAX} are allowed.")
        if has_duplicates:
            st.warning("Sequence names must be unique.")
        for err_text in invalid_errors[:3]:
            st.warning(err_text)

    # ── next stage button ─────────────────────────────────────────────────────

    _, _, col_next = st.columns(3)
    with col_next:
        if can_commit:
            if st.button(
                "Step 2: Alignment →",
                type="primary",
                use_container_width=True,
            ):
                seq_records: list[SelectedSequenceRecord] = []
                for slot in selected_seqs:
                    name = slot.get("name", "").strip()
                    seq = slot.get("sequence", "").strip().upper()
                    if slot.get("imported"):
                        seq_records.append(
                            SelectedSequenceRecord(
                                name=name,
                                sequence=seq,
                                imported_source_temp_id=slot["imported_source_id"],
                                imported_cand_temp_id=slot["imported_cand_id"],
                                imported_cand_original_name=slot.get(
                                    "imported_cand_original_name"
                                ),
                            )
                        )
                    else:
                        seq_records.append(
                            SelectedSequenceRecord(name=name, sequence=seq)
                        )

                src_records: list[ImportedSourceRecord] = []
                for src in st.session_state.get("ui_input_sources", []):
                    src_records.append(
                        ImportedSourceRecord(
                            temp_id=src["source_id"],
                            source_type=SourceType(src["source_type"]),
                            filename=src.get("filename"),
                            accession=src.get("accession"),
                            all_candidates=[
                                ImportedCandidateRecord(
                                    temp_id=c["cand_id"],
                                    original_name=c["name"],
                                    sequence=c["sequence"],
                                    description=c.get("description"),
                                    feature_type=c.get("feature_type"),
                                    feature_location=c.get("feature_location"),
                                )
                                for c in src["candidates"]
                            ],
                        )
                    )

                success, err_msg = commit_input(session, seq_records, src_records)
                if success:
                    mark_session_changed()
                    _clear_editing_state()
                    st.session_state["ui_input_editing"] = False
                    st.switch_page("pages/2_Alignment.py")
                else:
                    st.error(f"Commit failed: {err_msg}")
        else:
            st.button(
                "Step 2: Alignment →",
                disabled=True,
                use_container_width=True,
            )

render_processing_history_expander(session)
