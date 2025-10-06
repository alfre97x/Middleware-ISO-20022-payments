# Upgrade Notes

## What Changed

This update significantly enhances the `/v1/iso/verify` endpoint with new capabilities and fixes critical on-chain detection issues.

## New Features

### 1. Enhanced Verify Endpoint
- **New**: Accepts both `bundle_url` and `bundle_hash` inputs
- **New**: Automatic anchoring for missing on-chain evidence
- **New**: Database updates with transaction details
- **New**: Comprehensive debug logging

### 2. Debug Tools
- **New**: `POST /v1/debug/anchor` endpoint for direct hash anchoring
- **New**: Enhanced logging throughout the verification process

### 3. On-Chain Detection Fixes
- **Fixed**: Event topic calculation for Coston2
- **Fixed**: RPC provider block range limitations
- **Fixed**: POA chain compatibility issues
- **Fixed**: Bundle hash extraction from log data

## Breaking Changes

**None** - All changes are backward compatible.

## Migration Guide

### For Existing Integrations

**No changes required** - existing `bundle_url` parameter continues to work exactly as before.

### For New Integrations

You can now use the more efficient `bundle_hash` parameter:

```bash
# Old way (still works)
curl -X POST http://127.0.0.1:8000/v1/iso/verify \
  -H "Content-Type: application/json" \
  -d '{"bundle_url": "http://127.0.0.1:8000/files/{id}/evidence.zip"}'

# New way (more efficient)
curl -X POST http://127.0.0.1:8000/v1/iso/verify \
  -H "Content-Type: application/json" \
  -d '{"bundle_hash": "0x..."}'
```

### Environment Variables

**New required variables** for auto-anchoring functionality:

```bash
# Add to your .env file
ANCHOR_PRIVATE_KEY=0x<your_private_key_here>
```

**Optional variables** for fine-tuning:

```bash
# Optional: Adjust search range (default: 1000)
ANCHOR_LOOKBACK_BLOCKS=1000

# Optional: Streamlit CORS origin (default: http://localhost:8501)
STREAMLIT_ORIGIN=http://localhost:8501
```

## Performance Improvements

### Faster Verification
- **Chunked search**: Respects RPC provider limits (30 blocks max)
- **Optimized queries**: Searches recent blocks first
- **Reduced API calls**: Direct hash verification without download

### Better Error Handling
- **Graceful fallbacks**: POA chain timestamp issues handled
- **Detailed logging**: Debug information for troubleshooting
- **Auto-recovery**: Automatic anchoring for missing evidence

## Configuration Changes

### Database Schema
**No changes** - existing database structure is preserved.

### API Endpoints
**No changes** - all existing endpoints work as before.

### Smart Contract
**No changes** - uses existing `EvidenceAnchor` contract.

## Testing Your Upgrade

### 1. Verify Health Check
```bash
curl http://127.0.0.1:8000/v1/health
# Should return: {"status":"ok","ts":"..."}
```

### 2. Test Existing Functionality
```bash
# Test with bundle_url (existing functionality)
curl -X POST http://127.0.0.1:8000/v1/iso/verify \
  -H "Content-Type: application/json" \
  -d '{"bundle_url": "http://127.0.0.1:8000/files/{id}/evidence.zip"}'
```

### 3. Test New Functionality
```bash
# Test with bundle_hash (new functionality)
curl -X POST http://127.0.0.1:8000/v1/iso/verify \
  -H "Content-Type: application/json" \
  -d '{"bundle_hash": "0x..."}'
```

### 4. Test Auto-Anchoring
```bash
# Test debug anchor endpoint
curl -X POST http://127.0.0.1:8000/v1/debug/anchor \
  -H "Content-Type: application/json" \
  -d '{"bundle_hash": "0x..."}'
```

## Rollback Instructions

If you need to rollback:

1. **Revert code changes**:
   ```bash
   git checkout <previous-commit>
   ```

2. **Restart server**:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

3. **Verify functionality**:
   ```bash
   curl http://127.0.0.1:8000/v1/health
   ```

## Known Issues and Workarounds

### 1. RPC Provider Limits
**Issue**: Coston2 limits log queries to 30 blocks maximum.

**Workaround**: System automatically handles this with chunked search. For very old transactions (>1000 blocks), consider:
- Using a more recent transaction
- Implementing binary search for historical lookups
- Manual verification for critical old transactions

### 2. POA Chain Timestamps
**Issue**: Coston2's non-standard block structure causes timestamp errors.

**Workaround**: System automatically uses fallback timestamps. This doesn't affect functionality.

### 3. Private Key Security
**Issue**: Auto-anchoring requires private key in environment.

**Best Practices**:
- Use testnet keys only
- Never commit `.env` files
- Use environment variable injection in production
- Monitor gas usage and costs

## Support and Troubleshooting

### Debug Information
The system now provides comprehensive debug logging. Look for these messages in server logs:

```
DEBUG: VERIFY checking: 0x...
DEBUG: contract=0x262b1C649CE016717c62b9403E719C4801974CeF
DEBUG: Found X logs in chunk
DEBUG: MATCH FOUND: tx=...
```

### Common Issues
1. **Missing private key**: Add `ANCHOR_PRIVATE_KEY` to `.env`
2. **Insufficient funds**: Ensure key has FLR for gas fees
3. **RPC connectivity**: Check `FLARE_RPC_URL` is accessible
4. **Contract address**: Verify `ANCHOR_CONTRACT_ADDR` is correct

### Getting Help
- Check server logs for DEBUG messages
- Use debug endpoints to test functionality
- Verify environment configuration
- Test with known working transactions

## Next Steps

After successful upgrade:

1. **Monitor performance**: Watch for any slowdowns in verification
2. **Test auto-anchoring**: Ensure it works with your use cases
3. **Update documentation**: Share new capabilities with your team
4. **Consider optimizations**: Implement caching or binary search if needed

## Changelog

### Added
- `bundle_hash` parameter to `/v1/iso/verify`
- Automatic anchoring for missing on-chain evidence
- `POST /v1/debug/anchor` endpoint
- Comprehensive debug logging
- Chunked search for RPC provider limits
- POA chain compatibility

### Fixed
- On-chain detection for Coston2 transactions
- Event topic calculation
- Bundle hash extraction from log data
- Block timestamp handling for POA chains

### Changed
- Enhanced verify endpoint with auto-anchoring
- Improved error handling and logging
- Optimized search strategy for better performance

### Removed
- None - all existing functionality preserved
