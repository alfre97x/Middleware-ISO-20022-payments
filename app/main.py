from __future__ import annotations

import os
from uuid import uuid4
from datetime import datetime, date
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
import requests
from starlette.responses import StreamingResponse, RedirectResponse
import anyio
from .sse import stream_events, hub

# These local modules will be added in subsequent steps
# - app/schemas.py: Pydantic models for requests/responses
# - app/db.py: SQLAlchemy engine/session helpers
# - app/models.py: SQLAlchemy models (Receipt)
# - app/iso.py: ISO 20022 pain.001 generator + XSD validation
# - app/bundle.py: Deterministic ZIP bundle + signing
# - app/anchor.py: Flare (Coston2) anchoring + log queries
from . import schemas, db, models, iso, bundle  # type: ignore


ARTIFACTS_DIR = os.getenv("ARTIFACTS_DIR", "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

app = FastAPI(title="ISO 20022 Payments Middleware", version="0.1.0")

# CORS: Allow Streamlit localhost by default
streamlit_origin = os.getenv("STREAMLIT_ORIGIN", "http://localhost:8501")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[streamlit_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static serving of artifacts
# Files will live under artifacts/{receipt_id}/...
app.mount("/files", StaticFiles(directory=ARTIFACTS_DIR), name="files")
# Static UI (HTML/JS) for optional receipt pages/widgets
app.mount("/ui", StaticFiles(directory="ui"), name="ui")
app.mount("/embed", StaticFiles(directory="embed"), name="embed")


# Database setup
models.Base.metadata.create_all(bind=db.engine)


def get_session():
    session = db.SessionLocal()
    try:
        yield session
    finally:
        session.close()


@app.get("/v1/health")
def health() -> dict:
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}

@app.get("/v1/iso/events/{rid}")
async def sse_events(rid: str):
    # Server-Sent Events stream for live receipt updates (zero polling)
    return StreamingResponse(stream_events(rid), media_type="text/event-stream")

@app.get("/receipt/{rid}")
def receipt_redirect(rid: str):
    # Convenience route to the UI receipt page
    return RedirectResponse(url=f"/ui/receipt.html?rid={rid}", status_code=307)

@app.get("/embed/receipt")
def embed_receipt_redirect(rid: Optional[str] = None, theme: Optional[str] = None):
    # Convenience route to the embed widget without .html
    if not rid:
        return RedirectResponse(url="/", status_code=307)
    q = f"?rid={rid}"
    if theme:
        q += f"&theme={theme}"
    return RedirectResponse(url=f"/embed/receipt.html{q}", status_code=307)


@app.post("/v1/iso/record-tip", response_model=schemas.RecordTipResponse)
def record_tip(
    payload: schemas.TipRecordRequest,
    background_tasks: BackgroundTasks,
    session=Depends(get_session),
):
    # Idempotency: dedupe by (chain, tip_tx_hash)
    existing = (
        session.query(models.Receipt)
        .filter(
            models.Receipt.chain == payload.chain,
            models.Receipt.tip_tx_hash == payload.tip_tx_hash,
        )
        .one_or_none()
    )
    if existing:
        return schemas.RecordTipResponse(receipt_id=str(existing.id), status=existing.status)

    rid = uuid4()
    created_at = datetime.utcnow()

    receipt = models.Receipt(
        id=rid,
        reference=payload.reference,
        tip_tx_hash=payload.tip_tx_hash,
        chain=payload.chain,
        amount=payload.amount,
        currency=payload.currency,
        sender_wallet=payload.sender_wallet,
        receiver_wallet=payload.receiver_wallet,
        status="pending",
        created_at=created_at,
        anchored_at=None,
    )
    session.add(receipt)
    session.commit()

    # Background processing: XML -> bundle -> sign -> anchor -> update DB
    background_tasks.add_task(_process_receipt, str(rid), payload.callback_url)

    return schemas.RecordTipResponse(receipt_id=str(rid), status="pending")


def _process_receipt(receipt_id: str, callback_url: Optional[str] = None):
    # New session in background task
    session = db.SessionLocal()
    try:
        rec: Optional[models.Receipt] = session.get(models.Receipt, receipt_id)
        if not rec:
            return

        # Build a dict view for ISO and bundle metadata
        receipt_dict = {
            "id": str(rec.id),
            "reference": rec.reference,
            "tip_tx_hash": rec.tip_tx_hash,
            "chain": rec.chain,
            "amount": rec.amount,
            "currency": rec.currency,
            "sender_wallet": rec.sender_wallet,
            "receiver_wallet": rec.receiver_wallet,
            "status": rec.status,
            "created_at": rec.created_at,
        }

        # 1) Generate ISO XML (validate when XSD is present)
        xml_bytes = iso.generate_pain001(receipt_dict)

        # 2) Create deterministic bundle and sign
        zip_path, bundle_hash = bundle.create_bundle(receipt_dict, xml_bytes)

        # 3) Anchor on Flare (Coston2) if available
        rec.bundle_hash = bundle_hash
        anchored = False
        # Try Python web3 first, then Node fallback
        try:
            from . import anchor  # type: ignore
            txid, block_number = anchor.anchor_bundle(bundle_hash)
            rec.flare_txid = txid
            rec.status = "anchored"
            rec.anchored_at = datetime.utcnow()
            anchored = True
        except Exception:
            try:
                from . import anchor_node  # type: ignore
                txid, block_number = anchor_node.anchor_bundle(bundle_hash)
                rec.flare_txid = txid
                rec.status = "anchored"
                rec.anchored_at = datetime.utcnow()
                anchored = True
            except Exception:
                # Anchoring unavailable/failed; keep artifacts and mark failed
                rec.status = "failed"

        # 4) Persist artifact paths
        rec.xml_path = f"{ARTIFACTS_DIR}/{rec.id}/pain001.xml"
        rec.bundle_path = f"{ARTIFACTS_DIR}/{rec.id}/evidence.zip"
        session.commit()

        # 4b) Publish SSE event (best-effort)
        try:
            evt_payload = {
                "receipt_id": str(rec.id),
                "status": rec.status,
                "bundle_hash": rec.bundle_hash,
                "flare_txid": rec.flare_txid,
                "xml_url": f"/files/{rec.id}/pain001.xml",
                "bundle_url": f"/files/{rec.id}/evidence.zip",
                "created_at": rec.created_at.isoformat() if rec.created_at else None,
                "anchored_at": rec.anchored_at.isoformat() if rec.anchored_at else None,
            }
            anyio.from_thread.run(hub.publish, str(rec.id), evt_payload)  # type: ignore
        except Exception:
            pass

        # 5) Optional callback to Capella
        if callback_url:
            try:
                cb_payload = {
                    "receipt_id": str(rec.id),
                    "status": rec.status,
                    "bundle_hash": rec.bundle_hash,
                    "flare_txid": rec.flare_txid,
                    "xml_url": f"/files/{rec.id}/pain001.xml",
                    "bundle_url": f"/files/{rec.id}/evidence.zip",
                    "created_at": rec.created_at.isoformat() if rec.created_at else None,
                    "anchored_at": rec.anchored_at.isoformat() if rec.anchored_at else None,
                }
                # If PUBLIC_BASE_URL is set, prefix artifact URLs for external consumers
                base_url = os.getenv("PUBLIC_BASE_URL")
                if base_url:
                    cb_payload["xml_url"] = f"{base_url}{cb_payload['xml_url']}"
                    cb_payload["bundle_url"] = f"{base_url}{cb_payload['bundle_url']}"
                # Fire-and-forget callback
                requests.post(callback_url, json=cb_payload, timeout=15)
            except Exception:
                # Do not fail background task on callback errors
                pass
    except Exception:
        # Best-effort error handling; upgrade to structured logging in future
        if rec:
            rec.status = "failed"
            session.commit()
        raise
    finally:
        session.close()


@app.get("/v1/iso/receipts/{rid}", response_model=schemas.ReceiptResponse)
def get_receipt(rid: str, session=Depends(get_session)):
    rec: Optional[models.Receipt] = session.get(models.Receipt, rid)
    if not rec:
        raise HTTPException(status_code=404, detail="Receipt not found")

    xml_url = f"/files/{rid}/pain001.xml"
    bundle_url = f"/files/{rid}/evidence.zip"

    return schemas.ReceiptResponse(
        id=str(rec.id),
        status=rec.status,
        bundle_hash=rec.bundle_hash,
        flare_txid=rec.flare_txid,
        xml_url=xml_url,
        bundle_url=bundle_url,
        created_at=rec.created_at,
        anchored_at=rec.anchored_at,
    )


@app.post("/v1/iso/verify", response_model=schemas.VerifyResponse)
def verify(req: schemas.VerifyRequest):
    # Delegate to bundle.verify + anchor lookup
    verification = bundle.verify_bundle(req.bundle_url)

    matches = False
    txid = None
    anchored_at = None
    errors = list(verification.errors)

    # Attempt on-chain match via Python web3, then Node fallback
    try:
        from . import anchor  # type: ignore
        chain_info = anchor.find_anchor(verification.bundle_hash)
        matches = chain_info.matches
        txid = chain_info.txid
        anchored_at = chain_info.anchored_at
    except Exception:
        try:
            from . import anchor_node  # type: ignore
            chain_info = anchor_node.find_anchor(verification.bundle_hash)
            matches = chain_info.matches
            txid = chain_info.txid
            anchored_at = chain_info.anchored_at
        except Exception:
            errors.append("anchor_lookup_unavailable")

    return schemas.VerifyResponse(
        matches_onchain=matches,
        bundle_hash=verification.bundle_hash,
        flare_txid=txid,
        anchored_at=anchored_at,
        errors=errors,
    )
