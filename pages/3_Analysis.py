from __future__ import annotations

import dataclasses

import streamlit as st

from core.analysis.annotations import (
    add_or_update_amino_acid_annotation,
    add_region_annotation,
    delete_amino_acid_annotation,
    delete_region_annotation,
    update_region_annotation,
)
from core.analysis.export import (
    build_amino_acid_annotations_csv,
    build_metric_pairwise_deltas_csv,
    build_position_composition_csv,
    build_region_annotations_csv,
    build_sequences_and_alignment_fasta,
)
from core.constants import (
    AMINO_ACID_COLOR_PALETTE_LABELS,
    AMINO_ACID_COLOR_PALETTES,
    DEFAULT_AMINO_ACID_COLOR_PALETTE,
    DEFAULT_REGION_ANNOTATION_COLOR,
    STANDARD_AMINO_ACIDS,
)
from core.analysis.profiles import compute_profiles
from core.analysis.unified_view import build_unified_analysis_figure
from core.state import (
    clear_feedback,
    get_feedback,
    get_session,
    has_computed_profiles,
    has_valid_alignment,
    mark_session_changed,
    set_feedback,
    update_session_timestamp,
)
from components import render_pipeline_navigator, render_processing_history_expander, render_workflow_box

if "session" not in st.session_state:
    st.error("No active session. Go to the home page to start one.")
    st.stop()

session = get_session()
render_pipeline_navigator(session, "analysis")

st.title("Step 3: Analysis")

# Runtime feedback block
feedback = get_feedback()
if feedback:
    _dispatch = {"success": st.success, "error": st.error, "warning": st.warning}
    _dispatch.get(feedback["type"], st.info)(feedback["message"])
    clear_feedback()

render_workflow_box(session, "analysis")

if not has_valid_alignment(session):
    pass
else:

    # ── profiles computed (read-only) view ────────────────────────────────────

    if has_computed_profiles(session):
        profiles = session.analysis_stage.computed_profiles
        if profiles is not None:
            st.success(
                f"Analysis complete: {len(profiles.alignment_pairs)} pairs, "
                f"{profiles.alignment_length} positions."
            )

            # Sync palette widget state to session before chart build
            _PALETTE_WIDGET_KEY = "ui_aa_palette_selector"
            _palette_options = list(AMINO_ACID_COLOR_PALETTE_LABELS.keys())
            _palette_labels = [AMINO_ACID_COLOR_PALETTE_LABELS[k] for k in _palette_options]
            if _PALETTE_WIDGET_KEY in st.session_state:
                _widget_label = st.session_state[_PALETTE_WIDGET_KEY]
                if _widget_label in _palette_labels:
                    _widget_key = _palette_options[_palette_labels.index(_widget_label)]
                    if _widget_key != session.ui_settings.amino_acid_palette_key:
                        session.ui_settings = dataclasses.replace(
                            session.ui_settings, amino_acid_palette_key=_widget_key
                        )
                        update_session_timestamp(session)
                        mark_session_changed()

            palette_key = session.ui_settings.amino_acid_palette_key
            palette = AMINO_ACID_COLOR_PALETTES.get(
                palette_key, AMINO_ACID_COLOR_PALETTES[DEFAULT_AMINO_ACID_COLOR_PALETTE]
            )
            composition_mode = st.session_state.get("alignment_composition_display_mode", "Stacked Bars")

            unified_fig = build_unified_analysis_figure(
                profiles=profiles,
                composition_mode="symbols" if composition_mode == "Symbols" else "stacked",
                region_annotations=session.analysis_stage.region_annotations,
                amino_acid_annotations=session.analysis_stage.amino_acid_annotations,
                aligned_sequences=session.alignment_stage.aligned_sequences,
                palette=palette,
            )
            st.plotly_chart(unified_fig, width="stretch")

            ctrl_col1, ctrl_col2 = st.columns(2)
            with ctrl_col1:
                st.segmented_control(
                    "Alignment composition display",
                    options=["Stacked Bars", "Symbols"],
                    default="Stacked Bars",
                    selection_mode="single",
                    key="alignment_composition_display_mode",
                )
            with ctrl_col2:
                _current_index = (
                    _palette_options.index(palette_key)
                    if palette_key in _palette_options
                    else 0
                )
                st.selectbox(
                    "Amino acid color palette",
                    options=_palette_labels,
                    index=_current_index,
                    key=_PALETTE_WIDGET_KEY,
                )
            st.caption(
                "The amino-acid color palette affects only the visual encoding of residue "
                "symbols/classes in the composition chart. It does not affect alignment, "
                "hydropathy, polar requirement, composition counts, or exported analysis values."
            )

            # ── Region annotation management ──────────────────────────────────

            alignment_length = session.alignment_stage.alignment_length or 0
            with st.expander("Region Annotations", expanded=False):
                annotations = session.analysis_stage.region_annotations
                editing_id = st.session_state.get("ui_editing_region_ann_id")

                if annotations:
                    st.write(f"{len(annotations)} region annotation(s):")
                    for ann in annotations:
                        cols = st.columns([3, 2, 3, 1, 1, 1])
                        with cols[0]:
                            st.write(f"**{ann.label}**")
                        with cols[1]:
                            st.write(f"pos {ann.start_position}–{ann.end_position}")
                        with cols[2]:
                            if ann.note:
                                st.caption(ann.note)
                        with cols[3]:
                            st.markdown(
                                f'<span style="display:inline-block;width:18px;height:18px;'
                                f'background-color:{ann.color_hex};border:1px solid #ccc;'
                                f'border-radius:3px;vertical-align:middle"></span>',
                                unsafe_allow_html=True,
                            )
                        with cols[4]:
                            if st.button("Edit", key=f"edit_ann_{ann.id}"):
                                st.session_state["ui_editing_region_ann_id"] = ann.id
                                st.rerun()
                        with cols[5]:
                            if st.button("Delete", key=f"del_ann_{ann.id}"):
                                if editing_id == ann.id:
                                    del st.session_state["ui_editing_region_ann_id"]
                                delete_region_annotation(session, ann.id)
                                mark_session_changed()
                                st.rerun()
                else:
                    st.caption("No region annotations yet.")

                if editing_id:
                    editing_ann = next(
                        (a for a in annotations if a.id == editing_id), None
                    )
                    if editing_ann is None:
                        del st.session_state["ui_editing_region_ann_id"]
                        st.rerun()
                    else:
                        st.divider()
                        st.write(f"**Edit annotation: {editing_ann.label}**")
                        with st.form("edit_region_annotation_form"):
                            edit_label = st.text_input("Label", value=editing_ann.label)
                            ecol1, ecol2 = st.columns(2)
                            with ecol1:
                                edit_start = st.number_input(
                                    "Start position",
                                    min_value=1,
                                    max_value=alignment_length,
                                    value=editing_ann.start_position,
                                    step=1,
                                )
                            with ecol2:
                                edit_end = st.number_input(
                                    "End position",
                                    min_value=1,
                                    max_value=alignment_length,
                                    value=editing_ann.end_position,
                                    step=1,
                                )
                            edit_note = st.text_input(
                                "Note (optional)", value=editing_ann.note or ""
                            )
                            edit_color = st.color_picker(
                                "Region color",
                                value=editing_ann.color_hex,
                                key="edit_region_annotation_color",
                            )
                            save_edit = st.form_submit_button("Save changes")
                            cancel_edit = st.form_submit_button("Cancel")
                        if save_edit:
                            ok, err = update_region_annotation(
                                session,
                                editing_id,
                                edit_label,
                                int(edit_start),
                                int(edit_end),
                                alignment_length,
                                edit_note.strip() or None,
                                edit_color,
                            )
                            if ok:
                                del st.session_state["ui_editing_region_ann_id"]
                                mark_session_changed()
                                st.success("Annotation updated.")
                                st.rerun()
                            else:
                                st.error(f"Invalid annotation: {err}")
                        if cancel_edit:
                            del st.session_state["ui_editing_region_ann_id"]
                            st.rerun()

                if not editing_id:
                    st.divider()
                    st.write("**Add annotation**")
                    with st.form("add_region_annotation_form", clear_on_submit=True):
                        ann_label = st.text_input("Label", placeholder="e.g. Signal peptide")
                        col1, col2 = st.columns(2)
                        with col1:
                            ann_start = st.number_input(
                                "Start position",
                                min_value=1,
                                max_value=alignment_length,
                                value=1,
                                step=1,
                            )
                        with col2:
                            ann_end = st.number_input(
                                "End position",
                                min_value=1,
                                max_value=alignment_length,
                                value=alignment_length,
                                step=1,
                            )
                        ann_note = st.text_input(
                            "Note (optional)", placeholder="e.g. Cleaved signal sequence"
                        )
                        ann_color = st.color_picker(
                            "Region color",
                            value=DEFAULT_REGION_ANNOTATION_COLOR,
                            key="new_region_annotation_color",
                        )
                        submitted = st.form_submit_button("Add annotation")
                        if submitted:
                            ok, err = add_region_annotation(
                                session,
                                ann_label,
                                int(ann_start),
                                int(ann_end),
                                alignment_length,
                                ann_note.strip() or None,
                                ann_color,
                            )
                            if ok:
                                mark_session_changed()
                                st.success("Annotation added.")
                                st.rerun()
                            else:
                                st.error(f"Invalid annotation: {err}")

            # ── Amino-acid annotation management ──────────────────────────────

            with st.expander("Amino-acid Annotations", expanded=False):
                aa_annotations = session.analysis_stage.amino_acid_annotations
                if aa_annotations:
                    for ann in sorted(aa_annotations, key=lambda a: a.amino_acid):
                        cols = st.columns([1, 5, 1])
                        with cols[0]:
                            st.write(f"**{ann.amino_acid}**")
                        with cols[1]:
                            st.write(ann.note)
                        with cols[2]:
                            if st.button("Delete", key=f"del_aa_ann_{ann.id}"):
                                delete_amino_acid_annotation(session, ann.id)
                                mark_session_changed()
                                st.rerun()
                else:
                    st.caption("No amino-acid annotations yet.")

                st.divider()
                st.write("**Save annotation**")
                with st.form("add_aa_annotation_form", clear_on_submit=True):
                    ann_aa = st.selectbox(
                        "Amino acid",
                        options=list(STANDARD_AMINO_ACIDS),
                    )
                    ann_note = st.text_area(
                        "Note",
                        placeholder="e.g. Cysteine; may be relevant for disulfide bonding.",
                        max_chars=500,
                    )
                    submitted = st.form_submit_button("Save annotation")
                    if submitted:
                        ok, err = add_or_update_amino_acid_annotation(
                            session, ann_aa, ann_note
                        )
                        if ok:
                            mark_session_changed()
                            st.success("Annotation saved.")
                            st.rerun()
                        else:
                            st.error(f"Invalid annotation: {err}")

            # ── Export ────────────────────────────────────────────────────────

            with st.expander("Export", expanded=False):
                # FASTA (requires alignment only)
                st.write("**Sequences and alignment FASTA**")
                if st.button("Generate sequences_and_alignment.fasta", key="an_gen_fasta"):
                    st.session_state["ui_export_fasta"] = build_sequences_and_alignment_fasta(session)
                    st.rerun()
                if fasta_data := st.session_state.get("ui_export_fasta"):
                    st.download_button(
                        "Download sequences_and_alignment.fasta",
                        data=fasta_data,
                        file_name="sequences_and_alignment.fasta",
                        mime="text/plain",
                        key="an_dl_fasta",
                    )

                st.divider()
                st.write("**Pairwise metric deltas CSV**")
                if st.button("Generate metric_pairwise_deltas.csv", key="an_gen_pairwise"):
                    st.session_state["ui_export_pairwise_csv"] = build_metric_pairwise_deltas_csv(session)
                    st.rerun()
                if csv_data := st.session_state.get("ui_export_pairwise_csv"):
                    st.download_button(
                        "Download metric_pairwise_deltas.csv",
                        data=csv_data,
                        file_name="metric_pairwise_deltas.csv",
                        mime="text/csv",
                        key="an_dl_pairwise",
                    )

                st.divider()
                st.write("**Position composition CSV**")
                if st.button("Generate position_composition.csv", key="an_gen_composition"):
                    st.session_state["ui_export_composition_csv"] = build_position_composition_csv(session)
                    st.rerun()
                if csv_data := st.session_state.get("ui_export_composition_csv"):
                    st.download_button(
                        "Download position_composition.csv",
                        data=csv_data,
                        file_name="position_composition.csv",
                        mime="text/csv",
                        key="an_dl_composition",
                    )

                st.divider()
                st.write("**Region annotations CSV**")
                if session.analysis_stage.region_annotations:
                    if st.button("Generate region_annotations.csv", key="an_gen_region_ann"):
                        st.session_state["ui_export_region_ann_csv"] = build_region_annotations_csv(session)
                        st.rerun()
                    if csv_data := st.session_state.get("ui_export_region_ann_csv"):
                        st.download_button(
                            "Download region_annotations.csv",
                            data=csv_data,
                            file_name="region_annotations.csv",
                            mime="text/csv",
                            key="an_dl_region_ann",
                        )
                else:
                    st.caption("Not available: no region annotations exist.")

                st.divider()
                st.write("**Amino-acid annotations CSV**")
                if session.analysis_stage.amino_acid_annotations:
                    if st.button("Generate amino_acid_annotations.csv", key="an_gen_aa_ann"):
                        st.session_state["ui_export_aa_ann_csv"] = build_amino_acid_annotations_csv(session)
                        st.rerun()
                    if csv_data := st.session_state.get("ui_export_aa_ann_csv"):
                        st.download_button(
                            "Download amino_acid_annotations.csv",
                            data=csv_data,
                            file_name="amino_acid_annotations.csv",
                            mime="text/csv",
                            key="an_dl_aa_ann",
                        )
                else:
                    st.caption("Not available: no amino-acid annotations exist.")

    # ── not computed view ──────────────────────────────────────────────────────

    else:
        st.write("Ready to compute analysis profiles.")
        if st.button("Start analysis", type="primary"):
            with st.spinner("Computing profiles..."):
                success, err_msg = compute_profiles(session)
            if success:
                mark_session_changed()
                set_feedback("success", "Analysis profiles computed.")
            else:
                set_feedback("error", f"Analysis failed: {err_msg}")
            st.rerun()

# ── navigation ────────────────────────────────────────────────────────────────

st.divider()
nav_prev, _ = st.columns(2)
with nav_prev:
    if st.button("← Step 2: Alignment"):
        st.switch_page("pages/2_Alignment.py")

render_processing_history_expander(session)
