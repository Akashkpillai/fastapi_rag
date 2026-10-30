from app.schemas.document import PageContent
from app.services.chunker import MAX_WORDS, OVERLAP_WORDS, chunk_pages, split_text


def page(number: int, text: str) -> PageContent:
    return PageContent(page_id=f"d-p{number}", page_number=number, page_label=None, text=text)


def test_short_text_is_one_chunk():
    assert split_text("Just a short page.") == ["Just a short page."]


def test_long_text_respects_max_words_and_overlap():
    text = " ".join(f"w{i}" for i in range(1000))  # no sentence ends, so cuts land at MAX_WORDS
    pieces = split_text(text)

    assert len(pieces) > 1
    assert all(len(piece.split()) <= MAX_WORDS for piece in pieces)
    for first, second in zip(pieces, pieces[1:]):
        assert first.split()[-OVERLAP_WORDS:] == second.split()[:OVERLAP_WORDS]
    assert pieces[-1].split()[-1] == "w999"  # nothing lost at the end


def test_prefers_cutting_at_sentence_end():
    text = " ".join("This sentence has exactly eight words in it." for _ in range(100))
    for piece in split_text(text)[:-1]:
        assert piece.endswith(".")


def test_chunk_ids_are_unique(nist_pages):
    chunks = chunk_pages("test-doc", nist_pages)
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


def test_gv_sc_05_rows_keep_their_table_title(nist_pages):
    chunks = chunk_pages("test-doc", nist_pages)
    table_chunks = [c for c in chunks if "GV.SC-05" in c.text and 39 <= c.page_number <= 41]

    assert table_chunks
    for chunk in table_chunks:
        assert chunk.text.startswith("Table 5. GOVERN (GV)")


def test_continued_table_page_gets_previous_title(nist_pages):
    # Page 41 (printed 32) starts mid-table, without its own title
    assert nist_pages[40].text.find("Table 5.") == -1
    chunks = [c for c in chunk_pages("test-doc", nist_pages) if c.page_number == 41]
    assert chunks[0].text.startswith("Table 5. GOVERN (GV)")


def test_table_title_not_carried_past_prose_page():
    pages = [
        page(1, "Table 1. Example table\nCategory Subcategory\nGV.SC-01: first row"),
        page(2, "A page of ordinary prose with no row IDs."),
        page(3, "Prose that mentions GV.SC-02 in passing."),
    ]
    chunks = chunk_pages("d", pages)
    assert chunks[0].text.startswith("Table 1.")
    assert not chunks[2].text.startswith("Table 1.")
