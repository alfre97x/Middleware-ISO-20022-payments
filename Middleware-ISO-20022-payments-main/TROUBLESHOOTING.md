# Troubleshooting Guide

## Common Issues and Solutions

### 1. RPC Provider Block Range Limits

**Error Message**: `requested too many blocks from X to Y, maximum is set to 30`

**What's Happening**: Coston2 RPC provider limits log queries to 30 blocks maximum.

**Solution**: The system automatically handles this with chunked search (25-block chunks). If you still see this error:
- The transaction may be very old (>1000 blocks)
- Try using a more recent transaction
- Consider implementing binary search for historical lookups

**Debug Steps**:
```bash
# Check current block number
curl -X POST https://coston2-api.flare.network/ext/C/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Check if your transaction is in recent blocks
# Transaction block should be within last 1000 blocks of current block
```

### 2. POA Chain Timestamp Issues

**Error Message**: `The field extraData is 86 bytes, but should be 32. It is quite likely that you are connected to a POA chain.`

**What's Happening**: Coston2 is a Proof of Authority (POA) chain with non-standard block structure.

**Solution**: This is handled automatically by the system. The error is logged but doesn't affect functionality:
- System uses fallback timestamp (current time)
- Anchoring and verification still work correctly
- Only affects precise timestamp accuracy

**No Action Required**: This is expected behavior for POA chains.

### 3. Hash Format Issues

**Error Message**: `Invalid bundle_hash format - must be 0x followed by 64 hex chars`

**What's Happening**: Bundle hash is not properly formatted.

**Solution**: Ensure hash format is correct:
```bash
# Correct format
"0xac7d77802802090ade162d2b40d767fcf61fabc0de0709537931e03982bd6307"

# Common mistakes:
"ac7d77802802090ade162d2b40d767fcf61fabc0de0709537931e03982bd6307"  # Missing 0x
"0xac7d77802802090ade162d2b40d767fcf61fabc0de0709537931e03982bd6307"  # Too long
"0xac7d77802802090ade162d2b40d767fcf61fabc0de0709537931e03982bd630"   # Too short
```

### 4. Anchoring Failures

**Error Message**: `anchoring_failed` in verify response

**Possible Causes**:
1. **Missing Private Key**: `ANCHOR_PRIVATE_KEY` not set in `.env`
2. **Insufficient Funds**: Key doesn't have enough FLR for gas
3. **Wrong Contract**: `ANCHOR_CONTRACT_ADDR` is incorrect
4. **RPC Issues**: Network connectivity problems

**Solutions**:

#### Check Environment Variables
```bash
# Verify .env file contains:
FLARE_RPC_URL=https://coston2-api.flare.network/ext/C/rpc
ANCHOR_CONTRACT_ADDR=0x262b1C649CE016717c62b9403E719C4801974CeF
ANCHOR_PRIVATE_KEY=0x<your_private_key_here>
```

#### Check Private Key Funding
```bash
# Get account balance
curl -X POST https://coston2-api.flare.network/ext/C/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"eth_getBalance",
    "params":["0x<your_address>","latest"],
    "id":1
  }'

# If balance is 0, fund the account with FLR from Coston2 faucet
```

#### Test RPC Connectivity
```bash
# Test RPC endpoint
curl -X POST https://coston2-api.flare.network/ext/C/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

### 5. No On-Chain Matches Found

**Issue**: `matches_onchain: false` for transactions that should be anchored

**Possible Causes**:
1. **Transaction too old**: Beyond search range (>1000 blocks)
2. **Wrong contract address**: Using incorrect contract
3. **Event not emitted**: Transaction didn't call the contract
4. **Search timing**: Transaction not yet confirmed

**Solutions**:

#### Check Transaction Age
```bash
# Get current block
CURRENT_BLOCK=$(curl -s -X POST https://coston2-api.flare.network/ext/C/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' | jq -r '.result')

# Convert to decimal
CURRENT_DECIMAL=$((16#${CURRENT_BLOCK#0x}))

# Check if your transaction block is within 1000 blocks
# If not, it's too old for automatic search
```

#### Verify Contract Address
```bash
# Check if contract exists
curl -X POST https://coston2-api.flare.network/ext/C/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"eth_getCode",
    "params":["0x262b1C649CE016717c62b9403E719C4801974CeF","latest"],
    "id":1
  }'

# Should return non-empty result if contract exists
```

#### Manual Verification
```bash
# Use debug endpoint to manually anchor
curl -X POST http://127.0.0.1:8000/v1/debug/anchor \
  -H "Content-Type: application/json" \
  -d '{"bundle_hash": "0x..."}'
```

### 6. Server Startup Issues

**Error Message**: `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`

**What's Happening**: Port 8000 is already in use.

**Solution**:
```bash
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (Windows)
taskkill /PID <process_id> /F

# Or use different port
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### 7. Database Issues

**Error Message**: `index ix_receipts_status already exists`

**What's Happening**: Database schema conflict.

**Solution**:
```bash
# Delete existing database
rm dev.db

# Restart server (will recreate database)
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 8. Streamlit Connection Issues

**Error Message**: `Connection refused` when accessing Streamlit

**Solutions**:
1. **Check Streamlit is running**:
   ```bash
   streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
   ```

2. **Check API connection**:
   - Set API Base URL in Streamlit sidebar to `http://127.0.0.1:8000`
   - Ensure API server is running

3. **CORS issues**:
   - Check `STREAMLIT_ORIGIN` in environment
   - Ensure API allows Streamlit origin

## Debug Commands

### Check System Health
```bash
# API health
curl http://127.0.0.1:8000/v1/health

# Database connectivity (check server logs)
# Look for "Application startup complete"
```

### Test Anchoring
```bash
# Test with a known hash
curl -X POST http://127.0.0.1:8000/v1/debug/anchor \
  -H "Content-Type: application/json" \
  -d '{"bundle_hash": "0xac7d77802802090ade162d2b40d767fcf61fabc0de0709537931e03982bd6307"}'
```

### Monitor Server Logs
```bash
# Look for these debug messages:
# - "VERIFY checking: 0x..."
# - "Found X logs in chunk"
# - "MATCH FOUND: tx=..."
# - "DEBUG: topic0=..."
```

### Check Blockchain Connection
```bash
# Test RPC endpoint
curl -X POST https://coston2-api.flare.network/ext/C/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Should return current block number
```

## Performance Optimization

### For High-Volume Usage

1. **Increase Lookback Blocks**:
   ```bash
   # In .env
   ANCHOR_LOOKBACK_BLOCKS=2000
   ```

2. **Use Database Indexing**:
   ```sql
   -- Add indexes for better performance
   CREATE INDEX idx_receipts_bundle_hash ON receipts(bundle_hash);
   CREATE INDEX idx_receipts_status ON receipts(status);
   ```

3. **Implement Caching**:
   - Cache recent block ranges
   - Cache contract event topics
   - Use Redis for session storage

### For Production Deployment

1. **Environment Variables**:
   ```bash
   # Production .env
   FLARE_RPC_URL=https://coston2-api.flare.network/ext/C/rpc
   ANCHOR_CONTRACT_ADDR=0x262b1C649CE016717c62b9403E719C4801974CeF
   ANCHOR_PRIVATE_KEY=0x<production_key>
   DATABASE_URL=postgresql://user:pass@localhost/iso_mw
   ```

2. **Security**:
   - Use environment variable injection
   - Implement API authentication
   - Add rate limiting
   - Monitor gas usage

3. **Monitoring**:
   - Set up health checks
   - Monitor anchoring success rates
   - Track RPC response times
   - Alert on failures

## Getting Help

If you're still experiencing issues:

1. **Check the logs** for DEBUG messages
2. **Verify environment** variables are set correctly
3. **Test with debug endpoints** to isolate the issue
4. **Check blockchain connectivity** with RPC calls
5. **Verify private key** has sufficient funds

For additional support, include:
- Server logs with DEBUG messages
- Environment configuration (without private keys)
- Steps to reproduce the issue
- Expected vs actual behavior
