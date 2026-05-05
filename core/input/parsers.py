from __future__ import annotations

import io
import uuid
from dataclasses import dataclass

from Bio import SeqIO

from core.constants import STANDARD_AMINO_ACIDS

_VALID_AAS: frozenset[str] = frozenset(STANDARD_AMINO_ACIDS)

# DNA/RNA IUPAC single-letter codes. A sequence consisting only of these
# characters is treated as nucleotide-like and rejected for protein import.
_NUCLEOTIDE_CHARS: frozenset[str] = frozenset("ACGTURYSWKMBDHVNX")


@dataclass
class ParsedCandidate:
    cand_id: str
    name: str
    sequence: str
    description: str | None = None
    source_protein_name: str | None = None
    feature_type: str | None = None
    feature_location: str | None = None


def _new_temp_id() -> str:
    return f"tc_{uuid.uuid4().hex[:10]}"


def _is_nucleotide_like(seq_str: str) -> bool:
    upper = seq_str.upper()
    return bool(upper) and all(c in _NUCLEOTIDE_CHARS for c in upper)


def parse_fasta_file(
    filename: str, content: bytes
) -> tuple[list[ParsedCandidate], str | None]:
    try:
        text = content.decode("utf-8", errors="replace")
        records = list(SeqIO.parse(io.StringIO(text), "fasta"))
    except Exception as exc:
        return [], f"Could not parse FASTA file: {exc}"

    if not records:
        return [], "No records found in the FASTA file."

    candidates: list[ParsedCandidate] = []
    for record in records:
        raw = str(record.seq).strip().upper().replace(" ", "").replace("\n", "")

        if not raw:
            return [], f"Record '{record.id}' has an empty sequence."

        if _is_nucleotide_like(raw):
            return (
                [],
                f"Record '{record.id}' appears to be a nucleotide sequence. "
                "Only protein FASTA files are accepted.",
            )

        invalid = sorted({c for c in raw if c not in _VALID_AAS})
        if invalid:
            return (
                [],
                f"Record '{record.id}' contains invalid amino acid characters: "
                + ", ".join(f"'{c}'" for c in invalid)
                + ". Only the 20 standard amino acids are accepted.",
            )

        description = record.description.strip()
        # SeqIO sets description to "<id> <rest>" — strip the leading ID part.
        if description.startswith(record.id):
            description = description[len(record.id) :].strip()
        description = description or None

        candidates.append(
            ParsedCandidate(
                cand_id=_new_temp_id(),
                name=record.id,
                sequence=raw,
                description=description,
            )
        )

    return candidates, None


def _extract_mat_peptide_candidates(
    records: list,
) -> tuple[list[ParsedCandidate], str | None]:
    candidates: list[ParsedCandidate] = []
    for record in records:
        for feature in record.features:
            if feature.type != "mat_peptide":
                continue

            if "translation" in feature.qualifiers:
                trans = (
                    feature.qualifiers["translation"][0]
                    .strip()
                    .upper()
                    .rstrip("*")
                )
            else:
                try:
                    sub_seq = feature.location.extract(record.seq)
                    trans = str(sub_seq.translate(to_stop=True)).upper().strip()
                except Exception:
                    continue

            if not trans:
                continue

            invalid = sorted({c for c in trans if c not in _VALID_AAS})
            if invalid:
                # Skip features with non-standard residues rather than
                # failing the whole source — the caller checks for zero results.
                continue

            product = feature.qualifiers.get("product", [None])[0]
            note = feature.qualifiers.get("note", [None])[0]
            name = product or f"{record.id}_mat_peptide"

            source_protein_name: str | None = None
            if record.description and record.description != ".":
                source_protein_name = record.description

            candidates.append(
                ParsedCandidate(
                    cand_id=_new_temp_id(),
                    name=name,
                    sequence=trans,
                    description=note,
                    source_protein_name=source_protein_name,
                    feature_type="mat_peptide",
                    feature_location=str(feature.location),
                )
            )

    if not candidates:
        return (
            [],
            "No usable mat_peptide features with valid protein translations were found.",
        )

    return candidates, None


def parse_genbank_file(
    filename: str, content: bytes
) -> tuple[list[ParsedCandidate], str | None]:
    try:
        text = content.decode("utf-8", errors="replace")
        records = list(SeqIO.parse(io.StringIO(text), "genbank"))
    except Exception as exc:
        return [], f"Could not parse GenBank file: {exc}"

    if not records:
        return [], "No records found in the GenBank file."

    return _extract_mat_peptide_candidates(records)


def parse_genbank(raw_text: str) -> tuple[list[ParsedCandidate], str | None]:
    """Parse GenBank text directly (not from uploaded file bytes)."""
    try:
        records = list(SeqIO.parse(io.StringIO(raw_text), "genbank"))
    except Exception as exc:
        return [], f"Could not parse GenBank text: {exc}"

    if not records:
        return [], "No records found in the GenBank text."

    return _extract_mat_peptide_candidates(records)
