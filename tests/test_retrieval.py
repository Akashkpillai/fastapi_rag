from types import SimpleNamespace

import pytest

from app.services import retrieval


@pytest.mark.parametrize(
    "question, expected",
    [
        ("What happened to ID.SC-03 in CSF 2.0?", ["ID.SC-03"]),
        ("Compare PR.DS-11 and RC.RP-03 and PR.DS-11 again", ["PR.DS-11", "RC.RP-03"]),
        ("What is C-SCRM?", []),       # no digit: an acronym, not an ID
        ("Does SP 800-53 apply?", []),  # no letter in the joined part
        ("Who is the primary audience?", []),
    ],
)
def test_find_identifiers(question, expected):
    assert retrieval.find_identifiers(question) == expected


def fake_chunk(chunk_id: str, page_number: int):
    return SimpleNamespace(chunk_id=chunk_id, document_id="d", page_number=page_number, page_label=None, text="...")


@pytest.fixture
def fake_search(monkeypatch):
    # Replace the embedding model and both database searches with canned results
    calls = {}

    def setup(exact, semantic):
        monkeypatch.setattr(retrieval, "embed_query", lambda question: [0.0])

        def search_containing(session, embedding, terms, limit, document_id):
            calls["terms"], calls["limit"] = terms, limit
            return exact[:limit]

        monkeypatch.setattr(retrieval, "search_chunks_containing", search_containing)
        monkeypatch.setattr(retrieval, "search_chunks", lambda session, embedding, top_k, document_id: semantic[:top_k])
        return calls

    return setup


def test_exact_matches_come_first_without_duplicates(fake_search):
    page_44, page_41 = fake_chunk("p44", 44), fake_chunk("p41", 41)
    semantic = [(fake_chunk("p2", 2), 0.70), (page_44, 0.65), (fake_chunk("p3", 3), 0.60)]
    calls = fake_search(exact=[(page_44, 0.65), (page_41, 0.55)], semantic=semantic)

    results = retrieval.retrieve(None, "What happened to ID.SC-03?", top_k=4)

    assert calls["terms"] == ["ID.SC-03"]
    assert [r.page_number for r in results] == [44, 41, 2, 3]  # page 44 isn't repeated
    assert [r.exact_match for r in results] == [True, True, False, False]


def test_exact_matches_leave_room_for_semantic_ones(fake_search):
    exact = [(fake_chunk(f"e{i}", i), 0.6) for i in range(10)]
    calls = fake_search(exact=exact, semantic=[(fake_chunk("s", 99), 0.7)])

    results = retrieval.retrieve(None, "GV.SC-05", top_k=5)

    assert calls["limit"] == retrieval.MAX_EXACT_MATCHES
    assert results[-1].page_number == 99


def test_no_identifier_means_semantic_only(fake_search, monkeypatch):
    fake_search(exact=[], semantic=[(fake_chunk("s", 7), 0.7)])
    monkeypatch.setattr(retrieval, "search_chunks_containing", lambda *args: pytest.fail("should not run"))

    results = retrieval.retrieve(None, "Who is the audience?", top_k=5)
    assert [(r.page_number, r.exact_match) for r in results] == [(7, False)]
