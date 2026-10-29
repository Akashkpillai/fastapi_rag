import uuid

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

# from app.db.repository import save_document
from app.schemas.document import UploadSummary
from app.services.pdf_parser import InvalidPDFError, parse_pdf
from app.services.chunker import chunk_pages

router = APIRouter(prefix="/document", tags=["documents"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

@router.get("/{document_id}")
def one_document(document_id:int):
    return document_id

@router.get("/")
def document(limit: int = 5):
    return limit

@router.post("/upload", response_model=UploadSummary, status_code=201)
async def upload(file: UploadFile):
    # Check 1: what the client *says* the file is (easy to fake)
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are accepted")

    data = await file.read()

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 20 MB")

    # Check 2: what the file actually *is*: real PDFs start with "%PDF-"
    if b"%PDF-" not in data[:1024]:
        raise HTTPException(status_code=400, detail="File is not a valid PDF")

    document_id = uuid.uuid4().hex

    # Check 3: can it really be opened? (done inside parse_pdf)
    try:
        pages = await run_in_threadpool(parse_pdf, data, document_id)
    except InvalidPDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    usable_pages = [page for page in pages if page.text]
    empty_pages = [page.page_number for page in pages if not page.text]

    if not usable_pages:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found. This PDF appears to be scanned or "
                "image-only, so it needs OCR before it can be used.",
        )

    filename = file.filename or "unnamed.pdf"
    # save_document(document_id, filename, usable_pages)
    chunks = chunk_pages(document_id,usable_pages)

    return UploadSummary(
        document_id=document_id,
        filename=filename,
        page_count=len(pages),
        pages_with_text=len(usable_pages),
        empty_pages=empty_pages,
        chunk_count=len(chunks)
    )
