# ISO 20022 Payments Middleware (PoC)

A prototype middleware that ingests on-chain tips (Capella on Flare/Coston2), produces ISO 20022 pain.001.001.09 XML, builds a deterministic evidence bundle, anchors the bundle hash on Flare (Coston2), and exposes REST APIs, a Streamlit admin panel, and zero‑polling UI pages/widgets.

- API (FastAPI) with background jobs
- ISO 20022 generation (pain.001.001.09)
- Deterministic evidence.zip + manifest + signature
- Flare (Coston2) anchoring (event-only contract)
- Streamlit admin (optional)
- Zero‑polling live page and embed widget using SSE
- Capella integration package (Next.js 14 routes + client)

## What this prototype does (step-by-step)

1) Client (e.g., Capella) calls `POST /v1/iso/record-tip` after a successful tip, passing:
   - `tip_tx_hash`, `chain` (`"coston2"`), `amount` (string to preserve decimals), `currency` (`"FLR"`), `sender_wallet`, `receiver_wallet`, `reference` (`"capella:tip:<id>"`)
   - Optional: `callback_url` for server-to-server notification (no polling)
2) API returns `{"receipt_id":"<uuid>","status":"pending"}` immediately.
3) Background task:
   - Builds ISO 20022 pain.001.001.09 XML (CstmrCdtTrfInitn)
   - Creates deterministic `evidence.zip` with manifest and writes `signature.sig` alongside it
   - Anchors the bundle hash on Coston2 via `EvidenceAnchor` (event-only)
   - Updates the receipt to `status="anchored"` with `flare_txid`, `bundle_hash`
   - Emits an SSE update on `/v1/iso/events/{id}`; if `callback_url` provided, POSTs results to that URL
4) Clients retrieve:
   - `GET /v1/iso/receipts/{id}` for status and artifact links
   - Shareable live page: `/receipt/{id}`
   - Embeddable widget: `/embed/receipt?rid={id}`
   - Verify bundle: `POST /v1/iso/verify` with the bundle URL

## Repository structure

- `app/`
  - `main.py` (routes, background tasks, SSE endpoints)
  - `iso.py` (ISO 20022 pain.001.001.09 generator)
  - `bundle.py` (deterministic zip + signature + verification)
  - `anchor.py` / `anchor_node.py` (anchoring and event lookup with Node fallback)
  - `sse.py` (in-memory SSE hub)
  - `models.py`, `db.py`, `schemas.py` (SQLAlchemy + Pydantic)
- `ui/receipt.html` (live page, auto-updates via SSE)
- `embed/receipt.html` and `embed/receipt` (compact widget, iframe-friendly)
- `streamlit_app.py` (admin console)
- `contracts/` (Solidity contract, ABI, deployed.json)
- `capella_integration/` (copy into Capella project: client + route handlers)
- `scripts/` (deploy, anchor, find, smoke tests)
- `schemas/` (README for XSD placement)

## Prerequisites

- Python 3.11
- Node.js 18+ (for Node anchoring scripts; optional)
- (Optional) Docker Desktop for compose
- Git

## Contract and environment

- Coston2 contract `EvidenceAnchor` deployed at:
  - `0x262b1C649CE016717c62b9403E719C4801974CeF`
- `.env.example` (non-secret, committed):
  ```
  FLARE_RPC_URL=https://coston2-api.flare.network/ext/C/rpc
  ANCHOR_CONTRACT_ADDR=0x262b1C649CE016717c62b9403E719C4801974CeF
  ```
- Secrets (NOT committed; set locally or via CI secrets):
  - `ANCHOR_PRIVATE_KEY=0x<your_private_key>` (funded Coston2 key)

## Quickstart (Local)

1) Install dependencies
   ```
   pip install -r requirements.txt
   ```

2) Start API
   ```
   uvicorn app.main:app --reload --port 8000
   ```
   - Open docs: http://127.0.0.1:8000/docs

3) Create a test receipt (Windows CMD example)
   ```
   curl -X POST http://127.0.0.1:8000/v1/iso/record-tip ^
     -H "Content-Type: application/json" ^
     -d "{\"tip_tx_hash\":\"0xabc\",\"chain\":\"coston2\",\"amount\":\"0.000000000000000001\",\"currency\":\"FLR\",\"sender_wallet\":\"0xS\",\"receiver_wallet\":\"0xR\",\"reference\":\"demo:tip:1\"}"
   ```
   Response: `{"receipt_id":"<uuid>","status":"pending"}`

4) Live viewing (zero polling)
   - Full page: `http://127.0.0.1:8000/receipt/<receipt_id>` (redirects to `/ui/receipt.html?rid=...`)
   - Embeddable widget: `http://127.0.0.1:8000/embed/receipt?rid=<receipt_id>&theme=light`
   - SSE endpoint (for reference): `GET /v1/iso/events/<receipt_id>`

5) Retrieve artifacts
   - `GET /v1/iso/receipts/<receipt_id>` → returns `xml_url` and `bundle_url`
   - Example:
     ```
     curl http://127.0.0.1:8000/v1/iso/receipts/<receipt_id>
     ```

6) Verify the bundle
   ```
   curl -X POST http://127.0.0.1:8000/v1/iso/verify ^
     -H "Content-Type: application/json" ^
     -d "{\"bundle_url\":\"http://127.0.0.1:8000/files/<id>/evidence.zip\"}"
   ```

## Streamlit Admin UI

1) Launch
   ```
   streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
   ```
   UI: http://localhost:8501

2) Set API Base URL (sidebar) to `http://127.0.0.1:8000`

3) In “Receipts” tab:
   - Enter `receipt_id`, click “Fetch Receipt” to view data
   - “Zero‑polling options”:
     - Open live receipt page
     - Embedded widget (iframe) inline

## Capella Integration (Next.js 14 backend)

Use the files in `capella_integration/`:

- Copy `lib/isoClient.ts` into Capella (adjust alias to `@/lib/isoClient`).
- Copy these route handlers into `app/api/iso/...`:
  - `record-tip/route.ts` → proxies POST `/v1/iso/record-tip`
  - `receipts/[id]/route.ts` → proxies GET `/v1/iso/receipts/{id}`
  - `verify/route.ts` → proxies POST `/v1/iso/verify`
  - `callback/route.ts` (optional) → receive callback updates, update Prisma DB

Capella `.env`:
```
ISO_MIDDLEWARE_URL=http://127.0.0.1:8000
ISO_MW_TIMEOUT_MS=30000
```

Zero‑polling options for Capella:
- Simplest: link to `/receipt/{receipt_id}` or embed `/embed/receipt?rid={receipt_id}`
- Backend no‑polling: pass `callback_url` in `record-tip`; middleware will POST receipt results to Capella. Combine with server-side updates to avoid UI polling.

## ISO 20022 mapping

- Message: `pain.001.001.09` (`Document/CstmrCdtTrfInitn`)
- Namespace: `urn:iso:std:iso:20022:tech:xsd:pain.001.001.09`
- Required groups included:
  - `GrpHdr`: `MsgId`=reference, `CreDtTm`, `NbOfTxs`, `InitgPty/Nm`
  - `PmtInf`: `PmtInfId`=id, `PmtMtd`=TRF, `ReqdExctnDt`=date(created_at), `Dbtr` (WALLET mapping), `DbtrAcct` (Other/Id=wallet), `DbtrAgt`=NOTPROVIDED, `ChrgBr`=SLEV
  - `CdtTrfTxInf`: `PmtId/EndToEndId`=id, `Amt/InstdAmt` @Ccy, `CdtrAgt`=NOTPROVIDED, `Cdtr` (WALLET mapping), `CdtrAcct` (Other/Id=wallet), `RmtInf/Ustrd`=reference
- Wallet mapping: `Othr/Id` with `SchmeNm/Prtry = WALLET` (parties) and `WALLET_ACCOUNT` (accounts)
- Validation: place official XSDs under `./schemas` (see `schemas/README.md`). If absent, generation proceeds without runtime XSD validation.
- Currency note: PoC uses `"FLR"` for `InstdAmt/@Ccy`. Strict ISO 4217 may reject non-ISO codes; coordinate with downstream consumers for production.

## Docker Compose

```
docker compose up --build
```
- API: http://localhost:8000
- Streamlit: http://localhost:8501

## Troubleshooting

- Use `http://localhost:8501` in the browser (avoid `0.0.0.0` as a URL).
- If verify returns `signature_check_unavailable`, ensure PyNaCl is importable (or rely on on-chain log match).
- SSE behind a reverse proxy requires streaming-friendly settings; for cross-origin EventSource, allow the Capella origin via CORS.

## Security

- Never commit secrets (`.env`, private keys).
- For production: add API auth, rate limiting, secret management (vault), and broker-backed pub/sub for SSE (e.g., Redis channels) for HA.

## License

- MIT for code; ISO XSDs follow their own licensing per the provider.


---- 

Upcoming:
- Comprehensive Testing
- Implement Monitoring
- Performance Optimizations

