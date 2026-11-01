from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from docx import Document
from fastapi import HTTPException, UploadFile
from pypdf import PdfReader


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_EXTRACTED_CHARS = 120_000
MAX_PDF_PAGES = 40
MAX_ZIP_FILES = 800
MAX_ZIP_UNCOMPRESSED = 25 * 1024 * 1024


def _clean_text(value: str) -> str:
    value = value.replace("\x00", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()[:MAX_EXTRACTED_CHARS]


def _check_docx_container(data: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()

            if len(members) > MAX_ZIP_FILES:
                raise HTTPException(status_code=400, detail="DOCX contains too many files.")

            total = sum(item.file_size for item in members)

            if total > MAX_ZIP_UNCOMPRESSED:
                raise HTTPException(
                    status_code=400,
                    detail="DOCX expands beyond the allowed safety limit.",
                )

            names = {item.filename.lower() for item in members}

            if any(name.endswith(".bin") for name in names):
                raise HTTPException(
                    status_code=400,
                    detail="Macro/embedded binary DOCX files are not accepted.",
                )

            if "[content_types].xml" not in names:
                raise HTTPException(status_code=400, detail="Invalid DOCX package.")

    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid DOCX archive.") from exc


def extract_resume_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()

    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Résumé exceeds 5 MB.")

    try:
        if suffix == ".pdf":
            if not data.startswith(b"%PDF"):
                raise HTTPException(status_code=400, detail="Invalid PDF signature.")

            reader = PdfReader(io.BytesIO(data))

            if reader.is_encrypted:
                raise HTTPException(
                    status_code=400,
                    detail="Encrypted PDFs are not accepted.",
                )

            if len(reader.pages) > MAX_PDF_PAGES:
                raise HTTPException(status_code=400, detail="PDF has too many pages.")

            text = "\n".join(page.extract_text() or "" for page in reader.pages)

        elif suffix == ".docx":
            _check_docx_container(data)
            document = Document(io.BytesIO(data))
            text = "\n".join(
                paragraph.text
                for paragraph in document.paragraphs
                if paragraph.text.strip()
            )

        elif suffix == ".txt":
            text = data.decode("utf-8", errors="replace")

        else:
            raise HTTPException(
                status_code=415,
                detail="Only PDF, DOCX, and TXT résumés are accepted.",
            )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Résumé could not be safely parsed.",
        ) from exc

    cleaned = _clean_text(text)

    if len(cleaned) < 20:
        raise HTTPException(
            status_code=400,
            detail="The résumé did not contain enough extractable text.",
        )

    return cleaned
