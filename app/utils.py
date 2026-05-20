"""
utils.py — Utilidades de preprocesamiento y chunking de texto.
"""

import re
from app.config import settings


def chunk_text(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None
) -> list[str]:
    """
    Divide un texto en chunks con overlap.

    Estrategia:
    1. Limpieza básica del texto.
    2. Intenta dividir por párrafos primero (separadores naturales).
    3. Si el párrafo es mayor al chunk_size, lo subdivide por caracteres con overlap.

    Args:
        text: Texto a dividir.
        chunk_size: Tamaño máximo de cada chunk en caracteres.
        chunk_overlap: Solapamiento entre chunks en caracteres.

    Returns:
        Lista de strings (chunks).
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    # 1. Limpieza
    text = _clean_text(text)

    if not text:
        return []

    # 2. Si el texto es corto, no hace falta chunking
    if len(text) <= chunk_size:
        return [text]

    # 3. Dividir por párrafos/secciones
    raw_sections = _split_by_paragraphs(text)

    # 4. Subdividir secciones largas y construir chunks finales
    chunks = []
    for section in raw_sections:
        if len(section) <= chunk_size:
            if section.strip():
                chunks.append(section.strip())
        else:
            sub_chunks = _split_by_chars(section, chunk_size, chunk_overlap)
            chunks.extend(sub_chunks)

    # 5. Merge de chunks muy pequeños con el anterior
    chunks = _merge_small_chunks(chunks, min_size=100)

    return chunks


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Limpia el texto eliminando caracteres problemáticos."""
    # Normalizar saltos de línea
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Eliminar espacios múltiples (preservar saltos de línea)
    text = re.sub(r" {2,}", " ", text)
    # Eliminar líneas con solo espacios
    text = re.sub(r"\n[ \t]+\n", "\n\n", text)
    # Reducir más de 3 líneas vacías a 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_by_paragraphs(text: str) -> list[str]:
    """Divide por párrafos (doble salto de línea) o por oraciones."""
    # Primero intenta por párrafos
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) > 1:
        return paragraphs

    # Si no hay párrafos, divide por oraciones
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def _split_by_chars(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Divide un texto largo en chunks de tamaño fijo con overlap."""
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunks.append(text[start:].strip())
            break

        # Buscar el último espacio antes del límite para no cortar palabras
        split_pos = text.rfind(" ", start, end)
        if split_pos == -1 or split_pos <= start:
            split_pos = end  # No hay espacio, cortar duro

        chunks.append(text[start:split_pos].strip())
        start = split_pos - overlap  # Overlap hacia atrás

        if start < 0:
            start = 0

    return [c for c in chunks if c]


def _merge_small_chunks(chunks: list[str], min_size: int = 100) -> list[str]:
    """Combina chunks muy pequeños con el chunk anterior."""
    if not chunks:
        return []

    merged = [chunks[0]]
    for chunk in chunks[1:]:
        if len(chunk) < min_size and merged:
            merged[-1] = merged[-1] + " " + chunk
        else:
            merged.append(chunk)

    return merged
