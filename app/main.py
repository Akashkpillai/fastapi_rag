from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.api.routes import chat, documents, health
from app.db import models  # noqa: F401  (importing registers the tables on Base)
from app.db.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))  # enables pgvector in this database
    Base.metadata.create_all(engine)  # creates missing tables; leaves existing ones alone
    yield


STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(lifespan=lifespan)

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(chat.router)

# The chat page: plain HTML/CSS/JS, so there's no separate frontend build step
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def chat_page():
    return FileResponse(STATIC_DIR / "index.html")
