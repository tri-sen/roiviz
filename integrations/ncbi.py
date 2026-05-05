from __future__ import annotations

import urllib.error

from Bio import Entrez

Entrez.tool = "protein_sequence_analysis_prototype"


def fetch_genbank_text(accession: str, email: str) -> str:
    """
    Fetch raw GenBank text from NCBI nuccore.

    Returns: raw GenBank text on success.
    Raises: RuntimeError with user-facing message on failure.
    """
    accession = accession.strip()

    Entrez.email = email.strip()

    try:
        with Entrez.efetch(
            db="nuccore", id=accession, rettype="gb", retmode="text"
        ) as handle:
            text = handle.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 400:
            raise RuntimeError(
                f"Accession '{accession}' not found on NCBI nuccore."
            ) from exc
        raise RuntimeError(
            f"NCBI returned HTTP {exc.code} for '{accession}': {exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Network error fetching '{accession}' from NCBI: {exc.reason}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Error fetching '{accession}' from NCBI: {exc}"
        ) from exc

    if not text or not text.strip():
        raise RuntimeError(f"No data returned for accession '{accession}'.")

    # NCBI sometimes returns a plain-text error instead of raising HTTP 400.
    stripped = text.strip()
    if stripped.startswith("Error") or stripped.startswith("ID list is empty"):
        raise RuntimeError(
            f"NCBI error for '{accession}': {stripped[:200]}"
        )

    return text
