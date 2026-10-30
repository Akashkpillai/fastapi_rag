"""Measures how well the RAG pipeline answers questions about the NIST sample PDF.

    python -m eval.run_eval            # retrieval only: free, no OpenAI calls
    python -m eval.run_eval --answers  # also scores /question answers (one OpenAI call per question)

Needs the database running (docker compose up -d db). Uploads the sample PDF if it isn't stored yet.
Each question lists the viewer pages that contain its answer; an empty list means the PDF can't answer it.
"""
import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes.chat import MIN_SCORE
from app.db.models import DocumentRecord
from app.db.session import SessionLocal
from app.main import app

EVAL_DIR = Path(__file__).parent
SAMPLE_PDF = EVAL_DIR.parent / "data" / "sample_pdfs" / "NIST.CSWP.29.ipd.pdf"
TOP_K = 5


def find_or_upload_document(client: TestClient) -> str:
    with SessionLocal() as session:
        query = (
            select(DocumentRecord.id)
            .where(DocumentRecord.filename == SAMPLE_PDF.name)
            .order_by(DocumentRecord.created_at.desc())
        )
        document_id = session.scalar(query)
    if document_id:
        return document_id

    response = client.post(
        "/document/upload",
        files={"file": (SAMPLE_PDF.name, SAMPLE_PDF.read_bytes(), "application/pdf")},
    )
    response.raise_for_status()
    return response.json()["document_id"]


def first_hit_rank(pages: list[int], expected: set[int]) -> int | None:
    # 1-based position of the first retrieved chunk from an expected page
    return next((rank for rank, page in enumerate(pages, start=1) if page in expected), None)


def evaluate_retrieval(client, document_id, case) -> dict:
    response = client.post(
        "/search", json={"question": case["question"], "document_id": document_id, "top_k": TOP_K}
    )
    response.raise_for_status()
    results = response.json()["results"]
    pages = [result["page_number"] for result in results]
    return {
        "retrieved_pages": pages,
        "top_score": results[0]["score"] if results else 0.0,
        "rank": first_hit_rank(pages, set(case["expected_pages"])),
    }


def evaluate_answer(client, document_id, case) -> dict:
    response = client.post("/question", json={"question": case["question"], "document_id": document_id})
    response.raise_for_status()
    answer = response.json()
    expected = set(case["expected_pages"])

    if not expected:
        # The PDF can't answer this, so the right behaviour is to cite nothing
        correct = answer["cited_pages"] == []
        return {**answer, "cites_expected_page": None, "mentions_all": None, "correct": correct}

    cites_expected = bool(expected & set(answer["cited_pages"]))
    text = answer["answer"].lower()
    mentions_all = all(term.lower() in text for term in case["must_mention"])
    return {
        **answer,
        "cites_expected_page": cites_expected,
        "mentions_all": mentions_all,
        "correct": cites_expected and mentions_all,
    }


def percent(count: int, total: int) -> str:
    return f"{count}/{total} ({100 * count / total:.0f}%)" if total else "n/a"


def print_report(rows: list[dict], with_answers: bool) -> None:
    answerable = [row for row in rows if row["expected_pages"]]
    unanswerable = [row for row in rows if not row["expected_pages"]]

    print(f"\n{'#':>2}  {'top':>5}  {'rank':>4}  {'retrieved pages':<22}  question")
    for number, row in enumerate(rows, start=1):
        rank = row["rank"] or "-"
        pages = ",".join(map(str, row["retrieved_pages"]))
        flag = ""
        if with_answers:
            flag = "  OK " if row["correct"] else "  BAD"
        print(f"{number:>2}  {row['top_score']:.3f}  {rank:>4}  {pages:<22}{flag}  {row['question']}")

    print(f"\nRetrieval ({len(answerable)} answerable questions, top_k={TOP_K})")
    for k in (1, 3, 5):
        hits = sum(1 for row in answerable if row["rank"] and row["rank"] <= k)
        print(f"  hit@{k}: {percent(hits, len(answerable))}  (an expected page is in the top {k})")
    mrr = sum(1 / row["rank"] for row in answerable if row["rank"]) / len(answerable)
    print(f"  MRR:   {mrr:.3f}  (1.0 = the right page is always ranked first)")

    lowest_answerable = min(row["top_score"] for row in answerable)
    highest_unanswerable = max((row["top_score"] for row in unanswerable), default=0.0)
    rejected = sum(1 for row in unanswerable if row["top_score"] < MIN_SCORE)
    print(f"\nScore threshold (MIN_SCORE={MIN_SCORE})")
    print(f"  lowest top score, answerable:     {lowest_answerable:.3f}")
    print(f"  highest top score, unanswerable:  {highest_unanswerable:.3f}")
    print(f"  unanswerable stopped by MIN_SCORE: {percent(rejected, len(unanswerable))}")

    if with_answers:
        print("\nAnswers")
        cites = sum(1 for row in answerable if row["cites_expected_page"])
        mentions = sum(1 for row in answerable if row["mentions_all"])
        declined = sum(1 for row in unanswerable if row["correct"])
        print(f"  cites an expected page:        {percent(cites, len(answerable))}")
        print(f"  mentions the key facts:        {percent(mentions, len(answerable))}")
        print(f"  declines unanswerable ones:    {percent(declined, len(unanswerable))}")
        print(f"  overall correct:               {percent(sum(row['correct'] for row in rows), len(rows))}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--answers", action="store_true", help="also score /question answers (calls OpenAI)")
    args = parser.parse_args()

    cases = json.loads((EVAL_DIR / "questions.json").read_text(encoding="utf-8"))
    rows = []
    with TestClient(app) as client:
        document_id = find_or_upload_document(client)
        for case in cases:
            row = {**case, **evaluate_retrieval(client, document_id, case)}
            if args.answers:
                row.update(evaluate_answer(client, document_id, case))
            rows.append(row)

    print_report(rows, args.answers)
    results_path = EVAL_DIR / "results.json"
    results_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nFull results saved to {results_path}")


if __name__ == "__main__":
    main()
