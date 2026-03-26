from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

import docx2txt
import fitz


MAX_ATTACHMENT_COUNT = 5
MAX_ATTACHMENT_SIZE_BYTES = 5 * 1024 * 1024
TEXT_FILE_SUFFIXES = {
    '.txt',
    '.md',
    '.csv',
    '.json',
    '.py',
    '.js',
    '.ts',
    '.tsx',
    '.jsx',
    '.html',
    '.css',
    '.xml',
    '.yaml',
    '.yml',
    '.log',
}
SUPPORTED_ATTACHMENT_SUFFIXES = sorted({'.pdf', '.docx', *TEXT_FILE_SUFFIXES})


def _extract_pdf_text(raw_bytes: bytes) -> str:
    with fitz.open(stream=raw_bytes, filetype='pdf') as doc:
        return '\n'.join(page.get_text('text') for page in doc)


def _extract_docx_text(raw_bytes: bytes) -> str:
    return docx2txt.process(BytesIO(raw_bytes))


def _extract_plain_text(raw_bytes: bytes) -> str:
    return raw_bytes.decode('utf-8', errors='ignore')


def extract_text_from_bytes(filename: str, raw_bytes: bytes) -> str:
    suffix = Path(filename or '').suffix.lower()
    if suffix == '.pdf':
        return _extract_pdf_text(raw_bytes)
    if suffix == '.docx':
        return _extract_docx_text(raw_bytes)
    if suffix in TEXT_FILE_SUFFIXES:
        return _extract_plain_text(raw_bytes)
    raise ValueError(f'Unsupported file type: {suffix or "unknown"}')


async def extract_text_from_upload(filename: str, raw_bytes: bytes) -> str:
    return await asyncio.to_thread(extract_text_from_bytes, filename, raw_bytes)
