# Post-Setup Checklist

Use this checklist to verify your ISO 20022 Payments Middleware installation is working correctly.

## ✅ Basic Health Checks

### 1. Server Health
```bash
curl http://127.0.0.1:8000/v1/health
```
**Expected**: `{"status":"ok","ts":"2025-10-05T18:30:00.000000"}`

### 2. API Documentation
Visit: http://127.0.0.1:8000/docs
**Expected**: FastAPI interactive documentation loads

### 3. Database Connection
Check server logs for: `Application startup complete`
**Expected**: No database connection errors

## ✅ Core Functionality Tests

### 4. Record a Tip
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
    "reference": "test:tip:1"
  }'
```
**Expected**: `{"receipt_id":"<uuid>","status":"pending"}`

### 5. Get Receipt Status
```bash
curl http://127.0.0.1:8000/v1/iso/receipts/{receipt_id}
```
**Expected**: Receipt details with `bundle_url` and `bundle_hash`

### 6. Verify with Bundle Hash
```bash
curl -X POST http://127.0.0.1:8000/v1/iso/verify \
  -H "Content-Type: application/json" \
  -d '{"bundle_hash": "0x..."}'
```
**Expected**: `{"matches_onchain": true, "flare_txid": "0x...", "anchored_at": "..."}`

### 7. Verify with Bundle URL
```bash
curl -X POST http://127.0.0.1:8000/v1/iso/verify \
  -H "Content-Type: application/json" \
  -d '{"bundle_url": "http://127.0.0.1:8000/files/{id}/evidence.zip"}'
```
**Expected**: `{"matches_onchain": true, "flare_txid": "0x...", "anchored_at": "..."}`

## ✅ Blockchain Integration Tests

### 8. On-Chain Verification
Check that `flare_txid` resolves in Flare Coston2 explorer:
- Visit: https://coston2-explorer.flare.network/tx/{flare_txid}
- **Expected**: Transaction details visible

### 9. Contract Event Verification
Look for `EvidenceAnchored` event in transaction logs:
- **Expected**: Event with your bundle hash in the data field

### 10. Auto-Anchoring Test
```bash
# Test debug anchor endpoint
curl -X POST http://127.0.0.1:8000/v1/debug/anchor \
  -H "Content-Type: application/json" \
  -d '{"bundle_hash": "0x..."}'
```
**Expected**: `{"ok": true, "hash": "0x...", "txid": "0x...", "block": 12345}`

## ✅ Evidence Bundle Tests

### 11. Download Evidence Bundle
```bash
curl -O http://127.0.0.1:8000/files/{receipt_id}/evidence.zip
```
**Expected**: ZIP file downloads successfully

### 12. Verify Bundle Contents
Extract the ZIP and check contents:
- **Expected**: `pain001.xml`, `signature.sig`, `metadata.json`

### 13. Validate ISO 20022 XML
```bash
# Check XML structure
head -20 pain001.xml
```
**Expected**: Valid XML with ISO 20022 structure

### 14. Verify Digital Signature
```bash
# Check signature file
cat signature.sig
```
**Expected**: Base64-encoded signature

## ✅ UI Components Tests

### 15. Live Receipt Page
Visit: http://127.0.0.1:8000/receipt/{receipt_id}
**Expected**: Live receipt page loads with real-time updates

### 16. Embeddable Widget
Visit: http://127.0.0.1:8000/embed/receipt?rid={receipt_id}
**Expected**: Compact widget loads

### 17. Streamlit Admin Panel (Optional)
```bash
streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```
Visit: http://localhost:8501
**Expected**: Admin panel loads with receipt management

## ✅ Environment Configuration

### 18. Environment Variables
Check `.env` file contains:
```bash
FLARE_RPC_URL=https://coston2-api.flare.network/ext/C/rpc
ANCHOR_CONTRACT_ADDR=0x262b1C649CE016717c62b9403E719C4801974CeF
ANCHOR_PRIVATE_KEY=0x<your_private_key>
```

### 19. Private Key Funding
Verify your private key has sufficient FLR for gas fees:
- **Expected**: Balance > 0.01 FLR

### 20. RPC Connectivity
```bash
curl -X POST https://coston2-api.flare.network/ext/C/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```
**Expected**: Current block number returned

## ✅ Security Checks

### 21. No Secrets in Code
```bash
# Check for accidentally committed secrets
grep -r "0x[0-9a-fA-F]{64}" . --exclude-dir=.git
```
**Expected**: No private keys found in code

### 22. .env File Ignored
```bash
# Check .gitignore
grep -q "\.env" .gitignore
```
**Expected**: `.env` is in `.gitignore`

### 23. Database Security
Check database file permissions:
```bash
ls -la dev.db
```
**Expected**: Appropriate file permissions (not world-readable)

## ✅ Performance Tests

### 24. Response Times
Time API calls:
```bash
time curl http://127.0.0.1:8000/v1/health
```
**Expected**: Response time < 1 second

### 25. Concurrent Requests
Test multiple simultaneous requests:
```bash
# Run multiple verify requests in parallel
for i in {1..5}; do
  curl -X POST http://127.0.0.1:8000/v1/iso/verify \
    -H "Content-Type: application/json" \
    -d '{"bundle_hash": "0x..."}' &
done
wait
```
**Expected**: All requests complete successfully

### 26. Memory Usage
Monitor server memory usage:
```bash
# Check Python process memory
ps aux | grep uvicorn
```
**Expected**: Reasonable memory usage (< 500MB)

## ✅ Error Handling Tests

### 27. Invalid Bundle Hash
```bash
curl -X POST http://127.0.0.1:8000/v1/iso/verify \
  -H "Content-Type: application/json" \
  -d '{"bundle_hash": "invalid"}'
```
**Expected**: Proper error message returned

### 28. Missing Receipt
```bash
curl http://127.0.0.1:8000/v1/iso/receipts/nonexistent-id
```
**Expected**: 404 error with appropriate message

### 29. Malformed Request
```bash
curl -X POST http://127.0.0.1:8000/v1/iso/verify \
  -H "Content-Type: application/json" \
  -d '{"invalid": "data"}'
```
**Expected**: Validation error with field requirements

## ✅ Integration Tests

### 30. End-to-End Flow
Complete the full flow:
1. Record tip → Get receipt ID
2. Wait for processing → Check status
3. Verify bundle → Get on-chain confirmation
4. Download artifacts → Validate contents

**Expected**: All steps complete successfully

### 31. Auto-Anchoring Flow
Test the self-healing capability:
1. Record tip with missing on-chain evidence
2. Call verify endpoint
3. System automatically anchors
4. Verify returns `matches_onchain: true`

**Expected**: Automatic anchoring works without manual intervention

## ✅ Monitoring and Logging

### 32. Debug Logging
Check server logs for debug messages:
```
DEBUG: VERIFY checking: 0x...
DEBUG: Found X logs in chunk
DEBUG: MATCH FOUND: tx=...
```

### 33. Error Logging
Test error conditions and verify appropriate logging:
- Invalid inputs
- Network failures
- Blockchain errors

### 34. Performance Logging
Monitor response times and resource usage:
- API response times
- Database query performance
- Blockchain RPC calls

## ✅ Documentation Verification

### 35. API Documentation
Verify all endpoints are documented:
- Visit http://127.0.0.1:8000/docs
- Test each endpoint from the UI

### 36. Code Comments
Check that critical functions have proper documentation:
- `find_anchor()` function
- `verify()` endpoint
- Auto-anchoring logic

## ✅ Backup and Recovery

### 37. Database Backup
```bash
# Create database backup
cp dev.db dev.db.backup
```
**Expected**: Backup created successfully

### 38. Configuration Backup
```bash
# Backup configuration
cp .env .env.backup
```
**Expected**: Configuration backed up

## ✅ Production Readiness

### 39. Environment Security
- [ ] No hardcoded secrets
- [ ] Proper file permissions
- [ ] Secure key storage

### 40. Monitoring Setup
- [ ] Health check endpoint working
- [ ] Error logging configured
- [ ] Performance metrics available

## Troubleshooting Failed Checks

If any check fails:

1. **Check server logs** for error messages
2. **Verify environment variables** are set correctly
3. **Test individual components** to isolate issues
4. **Review troubleshooting guide** for common solutions
5. **Check blockchain connectivity** and funding

## Success Criteria

✅ **All checks pass** - System is ready for production use
⚠️ **Some checks fail** - Review troubleshooting guide
❌ **Multiple checks fail** - Check installation and configuration

## Next Steps

After completing the checklist:

1. **Document any issues** encountered during setup
2. **Configure monitoring** for production use
3. **Set up backups** for critical data
4. **Train team members** on new functionality
5. **Plan for scaling** as usage grows
