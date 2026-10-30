# PDF RAG Assistant

Upload PDFs and ask questions about them in a chat. Answers are written by an LLM using only the
retrieved PDF text, and every answer shows the pages it came from.

**Pipeline:** upload → extract text per page → chunk (200–350 words, table titles kept on table rows)
→ embed with `BAAI/bge-small-en-v1.5` → store in PostgreSQL + pgvector → hybrid search
(exact IDs like `GV.SC-05` + vector similarity) → answer with OpenAI, citing pages.

## Run it

1. Copy `.env.example` to `.env` and set `POSTGRES_PASSWORD` (in both places) and `OPENAI_API_KEY`.
2. Start everything:

   ```
   docker compose up -d --build
   ```

3. Open http://localhost:8000 for the chat, or http://localhost:8000/docs for the API.

The first upload downloads the embedding model (~130 MB); it's cached in the `models` volume after that.

## Develop locally

Run only the database in Docker and the app from a virtual environment:

```
docker compose up -d db
python -m venv env
env\Scripts\activate            # Windows (macOS/Linux: source env/bin/activate)
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Stop the `app` container first (`docker compose stop app`), since both use port 8000.

## API

| Method | Path | What it does |
|---|---|---|
| `POST` | `/document/upload` | Upload a PDF (max 20 MB); it's parsed, chunked, embedded and stored |
| `GET` | `/document/` | List documents with page and chunk counts |
| `GET` | `/document/{id}` | One document's details |
| `DELETE` | `/document/{id}` | Delete a document and its chunks |
| `POST` | `/search` | Retrieval only: the best-matching chunks with similarity scores |
| `POST` | `/question` | Retrieve, then answer with the LLM: `{answer, cited_pages, sources}` |

`/search` and `/question` take `{"question": "...", "document_id": "optional", "top_k": 5}`.

## Tests

```
pytest                       # everything (integration tests need the database running)
pytest -m "not integration"  # fast tests only: no database, no OpenAI
```

## Evaluation

`eval/questions.json` holds questions about the NIST sample PDF with the pages that contain each
answer, plus questions the PDF can't answer.

```
python -m eval.run_eval            # retrieval quality (hit@k, MRR): free
python -m eval.run_eval --answers  # also grades the LLM answers: one OpenAI call per question
```

Latest results (22 questions): the right page is in the top 3 for 18/18 answerable questions
(MRR 0.889), answers cite a correct page 18/18, and all 4 unanswerable questions are declined.
