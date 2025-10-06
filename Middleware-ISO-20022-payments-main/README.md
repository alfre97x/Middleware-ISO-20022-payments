# ISO 20022 Payments Middleware

A production-ready middleware that processes blockchain tips, generates ISO 20022 XML documents, creates evidence bundles, and anchors them on Flare blockchain. Features automatic anchoring, comprehensive verification, and zero-polling UI.

## Features

- 🚀 **FastAPI** with background processing
- 📄 **ISO 20022** pain.001.001.09 XML generation
- 🔗 **Blockchain anchoring** on Flare Coston2 testnet
- ✅ **Auto-verification** with on-chain detection
- 🎯 **Zero-polling UI** with Server-Sent Events
- 📊 **Streamlit admin panel** for monitoring
- 🔧 **Debug tools** for troubleshooting

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for Node.js anchoring fallback)
- **Git**
- **Funded Coston2 wallet** (for anchoring)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Setup

Create a `.env` file:

```bash
# Required for anchoring
FLARE_RPC_URL=https://coston2-api.flare.network/ext/C/rpc
ANCHOR_CONTRACT_ADDR=0x262b1C649CE016717c62b9403E719C4801974CeF
ANCHOR_PRIVATE_KEY=0x<your_private_key_here>

# Optional
ANCHOR_LOOKBACK_BLOCKS=1000
STREAMLIT_ORIGIN=http://localhost:8501
```

### 3. Start the Server

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Server will be available at: http://127.0.0.1:8000

### 4. Test the Flow

#### Record a Tip (PowerShell)
```powershell
$body = @{
    tip_tx_hash = "0xabc123"
    chain = "coston2"
    amount = "0.001"
    currency = "FLR"
    sender_wallet = "0xSender"
    receiver_wallet = "0xReceiver"
    reference = "demo:tip:1"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/iso/record-tip" -Method Post -ContentType "application/json" -Body $body
$receiptId = $response.receipt_id
Write-Host "Receipt ID: $receiptId"
```

#### Record a Tip (Linux/macOS)
```bash
curl -X POST http://127.0.0.1:8000/v1/iso/record-tip \
  -H "Content-Type: application/json" \
  -d '{
    "tip_tx_hash": "0xabc123",
    "chain": "coston2", 
    "amount": "0.001",
    "currency": "FLR",
    "sender_wallet": "0xSender",
    "receiver_wallet": "0xReceiver",
    "reference": "demo:tip:1"
  }'
```

#### Get Receipt Status
```bash
curl http://127.0.0.1:8000/v1/iso/receipts/{receipt_id}
```

#### Verify with Bundle URL
```bash
curl -X POST http://127.0.0.1:8000/v1/iso/verify \
  -H "Content-Type: application/json" \
  -d '{"bundle_url": "http://127.0.0.1:8000/files/{receipt_id}/evidence.zip"}'
```

#### Verify with Bundle Hash
```bash
curl -X POST http://127.0.0.1:8000/v1/iso/verify \
  -H "Content-Type: application/json" \
  -d '{"bundle_hash": "0x..."}'
```

## API Endpoints

### Core Endpoints

- `POST /v1/iso/record-tip` - Record a new tip
- `GET /v1/iso/receipts/{id}` - Get receipt status and artifacts
- `POST /v1/iso/verify` - Verify bundle (supports both URL and hash)
- `GET /v1/health` - Health check

### Debug Endpoints

- `POST /v1/debug/anchor` - Direct anchor a bundle hash
- `GET /v1/iso/events/{id}` - Server-Sent Events stream

### UI Endpoints

- `GET /receipt/{id}` - Live receipt page
- `GET /embed/receipt?rid={id}` - Embeddable widget

## Streamlit Admin Panel

### Start Streamlit (Optional)
```bash
streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Access at: http://localhost:8501

Features:
- View receipt details
- Download artifacts
- Live receipt preview
- Embeddable widget testing

## Docker Support

### Using Docker Compose
```bash
docker compose up --build
```

Services:
- **API**: http://localhost:8000
- **Streamlit**: http://localhost:8501
- **PostgreSQL**: localhost:5432

### Environment Variables for Docker
```bash
# Add to docker-compose.yml or .env
FLARE_RPC_URL=https://coston2-api.flare.network/ext/C/rpc
ANCHOR_CONTRACT_ADDR=0x262b1C649CE016717c62b9403E719C4801974CeF
ANCHOR_PRIVATE_KEY=0x<your_private_key>
```

## Troubleshooting

### Common Issues

#### 1. RPC Block Range Limits
**Error**: `requested too many blocks from X to Y, maximum is set to 30`

**Solution**: The system automatically handles this with chunked search. If you see this error, it means the transaction is very old and may need manual verification.

#### 2. POA Chain Timestamp Issues
**Error**: `The field extraData is 86 bytes, but should be 32`

**Solution**: This is normal for Coston2 (Proof of Authority chain). The system handles this automatically with fallback timestamps.

#### 3. Double 0x Prefix in Hashes
**Error**: Hash comparison fails with double `0x` prefix

**Solution**: Ensure your bundle hash is properly formatted as `0x` followed by 64 hex characters.

#### 4. Anchoring Failures
**Error**: `anchoring_failed` in verify response

**Solutions**:
- Ensure `ANCHOR_PRIVATE_KEY` is set in `.env`
- Verify the key has sufficient FLR for gas fees
- Check that `ANCHOR_CONTRACT_ADDR` is correct
- Ensure RPC endpoint is accessible

#### 5. No On-Chain Matches
**Issue**: `matches_onchain: false` for known transactions

**Solutions**:
- Wait a few minutes for transaction confirmation
- Check if the transaction is in the search range (last 1000 blocks)
- Verify the contract address is correct
- Use debug endpoint to manually anchor: `POST /v1/debug/anchor`

### Debug Commands

#### Check Server Health
```bash
curl http://127.0.0.1:8000/v1/health
```

#### Test Anchoring
```bash
curl -X POST http://127.0.0.1:8000/v1/debug/anchor \
  -H "Content-Type: application/json" \
  -d '{"bundle_hash": "0x..."}'
```

#### View Server Logs
```bash
# Look for DEBUG messages in server output
# Key indicators:
# - "VERIFY checking: 0x..."
# - "Found X logs in chunk"
# - "MATCH FOUND: tx=..."
```

## Architecture

### Core Components

- **`app/main.py`** - FastAPI routes and background tasks
- **`app/anchor.py`** - Blockchain anchoring and verification
- **`app/bundle.py`** - Evidence bundle creation and validation
- **`app/iso.py`** - ISO 20022 XML generation
- **`app/sse.py`** - Server-Sent Events for real-time updates

### Database Schema

```sql
receipts (
  id UUID PRIMARY KEY,
  reference TEXT UNIQUE,
  tip_tx_hash TEXT,
  chain TEXT,
  amount NUMERIC,
  currency TEXT,
  sender_wallet TEXT,
  receiver_wallet TEXT,
  status TEXT, -- pending/anchored/failed
  bundle_hash TEXT,
  flare_txid TEXT,
  created_at TIMESTAMP,
  anchored_at TIMESTAMP
)
```

### Smart Contract

**Contract**: `EvidenceAnchor` at `0x262b1C649CE016717c62b9403E719C4801974CeF`

**Event**: `EvidenceAnchored(bytes32 bundleHash, address sender, uint256 ts)`

**Function**: `anchorEvidence(bytes32 bundleHash)`

## Development

### Project Structure
```
├── app/                    # FastAPI application
│   ├── main.py            # Routes and background tasks
│   ├── anchor.py          # Blockchain operations
│   ├── bundle.py          # Evidence bundle handling
│   ├── iso.py             # ISO 20022 generation
│   └── ...
├── contracts/             # Smart contract files
├── ui/                    # Frontend components
├── embed/                 # Embeddable widgets
├── capella_integration/   # Capella integration code
└── scripts/               # Utility scripts
```

### Adding New Features

1. **New API Endpoints**: Add to `app/main.py`
2. **Database Changes**: Update `app/models.py` and create migration
3. **Blockchain Operations**: Extend `app/anchor.py`
4. **UI Components**: Add to `ui/` or `embed/`

## Security Notes

- **Never commit `.env` files** - they contain private keys
- **Use testnet keys only** - Coston2 is a test network
- **Rate limit API endpoints** in production
- **Validate all inputs** before processing
- **Monitor gas usage** for anchoring operations

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review server logs for DEBUG messages
3. Test with the debug endpoints
4. Verify environment configuration