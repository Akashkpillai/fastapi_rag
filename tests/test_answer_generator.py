from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.schemas.chat import RetrievedChunk
from app.services import answer_generator


def chunk(page_number: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"c{page_number}", document_id="d", page_number=page_number,
        page_label=None, text=f"Text from page {page_number}", score=0.7,
    )


@pytest.fixture
def fake_openai(monkeypatch):
    # Stands in for the OpenAI client: records the request and returns a canned reply
    calls = {}

    def use_reply(reply):
        def parse(**kwargs):
            calls.update(kwargs)
            return SimpleNamespace(output_parsed=reply)
        client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
        monkeypatch.setattr(answer_generator, "get_client", lambda: client)
        return calls

    return use_reply


def test_sends_excerpts_labelled_with_pages(fake_openai):
    calls = fake_openai(answer_generator.ModelAnswer(answer="ok", cited_pages=[]))
    answer_generator.generate_answer("What is GV.SC-05?", [chunk(39), chunk(40)])

    assert "[Page 39]\nText from page 39" in calls["input"]
    assert "Question: What is GV.SC-05?" in calls["input"]
    assert calls["instructions"] == answer_generator.SYSTEM_PROMPT
    assert calls["text_format"] is answer_generator.ModelAnswer


def test_drops_pages_that_were_not_sent(fake_openai):
    fake_openai(answer_generator.ModelAnswer(answer="ok", cited_pages=[40, 99, 40, 39]))
    result = answer_generator.generate_answer("q", [chunk(39), chunk(40)])
    assert result.cited_pages == [39, 40]  # 99 removed, duplicates merged, sorted


def test_refusal_raises(fake_openai):
    fake_openai(None)
    with pytest.raises(answer_generator.AnswerGenerationError):
        answer_generator.generate_answer("q", [chunk(1)])


def test_empty_api_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    answer_generator.get_client.cache_clear()
    try:
        with pytest.raises(answer_generator.MissingAPIKeyError):
            answer_generator.get_client()
    finally:
        answer_generator.get_client.cache_clear()
