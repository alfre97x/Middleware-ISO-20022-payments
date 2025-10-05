# PR: Enhanced Verify Endpoint with Auto-Anchoring and On-Chain Detection

## Summary

This PR significantly enhances the `/v1/iso/verify` endpoint to support both `bundle_url` and `bundle_hash` inputs, implements automatic anchoring for missing on-chain evidence, and fixes critical issues with on-chain verification on Coston2 testnet.

## Why These Changes Were Needed

The original verify endpoint had several critical limitations:

1. **Only supported `bundle_url`** - couldn't verify with just a hash
2. **Failed to detect anchored bundles** - returned `matches_onchain: False` even for successfully anchored transactions
3. **No auto-anchoring capability** - required manual intervention for missing on-chain evidence
4. **RPC provider limitations** - couldn't handle Coston2's 30-block query limit
5. **POA chain compatibility** - failed on Coston2's non-standard block structure

## What Changed (File-by-File)

### `app/schemas.py`
- **Modified `VerifyRequest`**: Now accepts either `bundle_url` (HttpUrl) or `bundle_hash` (str) with validation
- **Added model validator**: Ensures exactly one of the two fields is provided
- **Why**: Enables flexible verification with either URL or direct hash input

### `app/main.py`
- **Enhanced verify handler**: Added comprehensive debug logging and hash calculation logic
- **Added auto-anchoring**: If bundle not found on-chain, automatically attempts to anchor it
- **Added database updates**: Updates receipt with `flare_txid`, `status="anchored"`, `anchored_at`
- **Added debug route**: `POST /v1/debug/anchor` for direct hash anchoring
- **Why**: Provides self-healing verification and better debugging capabilities

### `app/anchor.py`
- **Fixed event topic calculation**: Manual keccak calculation instead of broken `_get_event_topic()`
- **Implemented chunked search**: 25-block chunks to respect RPC provider limits
- **Fixed POA chain handling**: Graceful fallback for Coston2's non-standard block structure
- **Fixed bundle hash extraction**: Read from log data field instead of trying to decode indexed parameters
- **Added comprehensive debug logging**: Track every step of the verification process
- **Why**: Resolves all on-chain detection issues and provides detailed troubleshooting info

### `.env` (new template)
- **Added environment variable documentation**: Clear template with required variables
- **Why**: Ensures proper configuration for anchoring functionality

## How to Test

### 1. Basic Verification Flow
```bash
# Record a tip
curl -X POST http://127.0.0.1:8000/v1/iso/record-tip \
  -H "Content-Type: application/json" \
  -d '{"tip_tx_hash":"0xabc","chain":"coston2","amount":"0.001","currency":"FLR","sender_wallet":"0xS","receiver_wallet":"0xR","reference":"test:tip:1"}'

# Get receipt
curl http://127.0.0.1:8000/v1/iso/receipts/{receipt_id}

# Verify with bundle_hash
curl -X POST http://127.0.0.1:8000/v1/iso/verify \
  -H "Content-Type: application/json" \
  -d '{"bundle_hash":"0x..."}'

# Should return matches_onchain: true
```

### 2. Auto-Anchoring Flow
```bash
# Verify a hash that's not yet anchored
curl -X POST http://127.0.0.1:8000/v1/iso/verify \
  -H "Content-Type: application/json" \
  -d '{"bundle_hash":"0x..."}'

# Should automatically anchor and return matches_onchain: true
```

### 3. Debug Anchoring
```bash
# Direct anchor a hash
curl -X POST http://127.0.0.1:8000/v1/debug/anchor \
  -H "Content-Type: application/json" \
  -d '{"bundle_hash":"0x..."}'
```

## Risks

1. **RPC Provider Limits**: Coston2 has a 30-block limit for log queries - mitigated by chunked search
2. **POA Chain Compatibility**: Coston2's non-standard block structure - handled with fallback timestamps
3. **Auto-Anchoring Costs**: Automatic anchoring requires funded private key - documented in setup
4. **Performance**: Chunked search may be slower for very old transactions - acceptable for current use case

## Follow-ups

1. **Optimize Search Strategy**: Implement binary search for faster historical lookups
2. **Add Metrics**: Track anchoring success rates and performance
3. **Enhanced Error Handling**: More specific error messages for different failure modes
4. **Caching**: Cache recent block ranges to avoid repeated queries
5. **Monitoring**: Add alerts for anchoring failures or RPC issues

## Breaking Changes

- **None**: All changes are backward compatible
- **New optional fields**: `bundle_hash` parameter is optional alongside existing `bundle_url`

## Migration Guide

- **Existing integrations**: No changes required - `bundle_url` still works
- **New integrations**: Can now use `bundle_hash` for more efficient verification
- **Environment**: Add `ANCHOR_PRIVATE_KEY` to `.env` for auto-anchoring functionality
