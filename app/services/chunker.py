import re

from app.schemas.document import Chunk, PageContent

MIN_WORDS = 300
MAX_WORDS = 500
OVERLAP_WORDS = 50

WORD = re.compile(r"\S+\s*")                          # a word plus the whitespace after it
PARAGRAPH_BREAK = re.compile(r"\n\s*\n")              # a blank line
SENTENCE_END = re.compile(r"[.!?][\"')\]]?\s+$")      # word ending a sentence
TABLE_TITLE = re.compile(r"^Table \d+[.:].*$", re.MULTILINE)
ROW_ID = re.compile(r"\b[A-Z]{2}\.[A-Z]{2}-\d{2}\b")  # CSF IDs like GV.SC-05


def _best_cut(tokens: list[str], start: int, end: int, min_end: int) -> int:
    # Prefer ending at a paragraph, then at a sentence, else cut at max length
    for i in range(end, min_end, -1):
        if PARAGRAPH_BREAK.search(tokens[i - 1]):
            return i
    for i in range(end, min_end, -1):
        if SENTENCE_END.search(tokens[i - 1]):
            return i
    return end


def split_text(text: str) -> list[str]:
    tokens = WORD.findall(text.strip())
    if len(tokens) <= MAX_WORDS:
        return [text.strip()]  # short page: one chunk

    pieces = []
    start = 0
    while True:
        end = min(start + MAX_WORDS, len(tokens))
        if end < len(tokens):
            end = _best_cut(tokens, start, end, start + MIN_WORDS)
        pieces.append("".join(tokens[start:end]).strip())
        if end == len(tokens):
            return pieces
        start = end - OVERLAP_WORDS  # step back so the next chunk repeats the last 50 words


def find_table_header(page_text: str, heading_lines: int = 1) -> str | None:
    match = TABLE_TITLE.search(page_text)
    if not match:
        return None
    following = page_text[match.end():].strip().splitlines()[:heading_lines]
    return "\n".join([match.group(0).strip(), *following])


def chunk_pages(document_id: str, pages: list[PageContent]) -> list[Chunk]:
    chunks = []
    table_header = None
    for page in pages:
        # A table that continues from the previous page keeps that page's header
        own_header = find_table_header(page.text)
        if own_header:
            table_header = own_header
        elif not ROW_ID.search(page.text):
            table_header = None

        for index, piece in enumerate(split_text(page.text)):
            if table_header and ROW_ID.search(piece) and table_header not in piece:
                piece = f"{table_header}\n{piece}"
            chunks.append(
                Chunk(
                    chunk_id=f"{page.page_id}-c{index}",
                    document_id=document_id,
                    page_id=page.page_id,
                    page_number=page.page_number,
                    page_label=page.page_label,
                    chunk_index=index,
                    text=piece,
                )
            )
    return chunks
