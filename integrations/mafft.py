from __future__ import annotations

import os
import subprocess
import tempfile

from core.constants import MAFFT_OUTPUT_CAP

MAFFT_TIMEOUT_SECONDS: int = 120


def run_mafft(fasta_input: str) -> tuple[str, str, int, bool, bool]:
    """Run MAFFT via subprocess with FASTA written to a named temp file.

    Returns (stdout, stderr, return_code, stdout_truncated, stderr_truncated).
    Both stdout and stderr are capped at MAFFT_OUTPUT_CAP characters.
    """
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fasta", delete=False) as tmp:
            tmp.write(fasta_input)
            tmp_path = tmp.name

        result = subprocess.run(
            [
                "mafft",
                "--auto",
                "--amino",
                "--inputorder",
                "--quiet",
                "--thread",
                "1",
                tmp_path,
            ],
            shell=False,
            capture_output=True,
            text=True,
            timeout=MAFFT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return "", "mafft executable not found on PATH.", 1, False, False
    except subprocess.TimeoutExpired:
        timeout_msg = (
            f"MAFFT alignment timed out after {MAFFT_TIMEOUT_SECONDS} seconds."
            " Try a smaller input."
        )
        return "", timeout_msg, 1, False, False
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    stdout = result.stdout
    stderr = result.stderr
    stdout_truncated = len(stdout) > MAFFT_OUTPUT_CAP
    stderr_truncated = len(stderr) > MAFFT_OUTPUT_CAP

    return (
        stdout[:MAFFT_OUTPUT_CAP],
        stderr[:MAFFT_OUTPUT_CAP],
        result.returncode,
        stdout_truncated,
        stderr_truncated,
    )
