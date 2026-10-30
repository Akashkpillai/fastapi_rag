from contextlib import asynccontextmanager

from fastapi import FastAPI
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


app = FastAPI(lifespan=lifespan)

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(chat.router)
