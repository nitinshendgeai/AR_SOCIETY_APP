"""Documents filed against a voucher: the supplier's bill, a receipt, a photo of the work.

A voucher keeps a few files (a PDF or a picture), each up to 8 MB. They are read-only once filed: a wrong one is
removed and the right one filed. Anyone who may see the voucher may open them; filing and removing are for managers
(the accounts routes already require that).
"""
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.accounts.models.accounts import Voucher, VoucherDocument

MAX_BYTES = 8 * 1024 * 1024
MAX_PER_VOUCHER = 10
ALLOWED = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
           "image/heic": ".heic"}


def document_out(d: VoucherDocument) -> dict:
    return {"id": str(d.id), "file_name": d.file_name, "mime_type": d.mime_type, "size_bytes": d.size_bytes,
            "uploaded_by_name": d.uploader.full_name if d.uploader else None,
            "uploaded_at": d.created_at.isoformat() if d.created_at else None}


class VoucherDocumentService:
    def __init__(self, db: Session):
        self.db = db

    def list_for(self, voucher_id: UUID) -> List[VoucherDocument]:
        return (self.db.query(VoucherDocument).filter(VoucherDocument.voucher_id == voucher_id)
                .order_by(VoucherDocument.created_at).all())

    def counts(self, voucher_ids: List[UUID]) -> dict:
        """{voucher id: number of documents} for the vouchers that have any."""
        if not voucher_ids:
            return {}
        rows = (self.db.query(VoucherDocument.voucher_id, func.count(VoucherDocument.id))
                .filter(VoucherDocument.voucher_id.in_(voucher_ids)).group_by(VoucherDocument.voucher_id).all())
        return {vid: n for vid, n in rows}

    def add(self, voucher: Voucher, file_name: Optional[str], mime_type: Optional[str], data: bytes,
            user) -> VoucherDocument:
        mime = (mime_type or "").lower()
        if mime not in ALLOWED:
            raise HTTPException(422, "Attach a PDF or a picture (JPG, PNG, WEBP or HEIC).")
        if not data:
            raise HTTPException(422, "The file is empty.")
        if len(data) > MAX_BYTES:
            raise HTTPException(422, f"The file is over the {MAX_BYTES // (1024 * 1024)} MB limit.")
        if len(self.list_for(voucher.id)) >= MAX_PER_VOUCHER:
            raise HTTPException(422, f"A voucher keeps at most {MAX_PER_VOUCHER} documents.")
        name = (file_name or "").strip().replace("\\", "/").split("/")[-1] or f"document{ALLOWED[mime]}"
        doc = VoucherDocument(society_id=voucher.society_id, voucher_id=voucher.id, file_name=name[:255],
                              mime_type=mime, size_bytes=len(data), data=data,
                              uploaded_by=user.id if user else None)
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get(self, document_id: UUID) -> VoucherDocument:
        doc = self.db.get(VoucherDocument, document_id)
        if doc is None:
            raise HTTPException(404, "Document not found")
        return doc

    def remove(self, doc: VoucherDocument) -> None:
        self.db.delete(doc)
        self.db.commit()
