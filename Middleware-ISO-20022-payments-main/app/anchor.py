from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Any, Dict, List

from eth_account import Account  # type: ignore
from eth_utils import to_checksum_address  # type: ignore
from hexbytes import HexBytes  # type: ignore
from web3 import Web3  # type: ignore
from web3.contract import Contract  # type: ignore
from web3.exceptions import ContractLogicError  # type: ignore

from .schemas import ChainMatch

# add fixes
import logging

# Set up debug logging
logger = logging.getLogger("anchor")
logger.setLevel(logging.DEBUG)
logger.debug("FLARE_RPC_URL=%s", os.getenv("FLARE_RPC_URL"))
logger.debug("ANCHOR_CONTRACT_ADDR=%s", os.getenv("ANCHOR_CONTRACT_ADDR"))
logger.debug("ADDR_ENV=%s", os.getenv("ADDR_ENV"))
logger.debug("ANCHOR_PRIVATE_KEY set? %s", bool(os.getenv("ANCHOR_PRIVATE_KEY")))


# Environment/config
FLARE_RPC = os.getenv("FLARE_RPC_URL", "https://coston2-api.flare.network/ext/C/rpc")
PRIVATE_KEY = os.getenv("ANCHOR_PRIVATE_KEY")  # hex string 0x...
CONTRACT_ADDR = os.getenv("ANCHOR_CONTRACT_ADDR")  # 0x...
ABI_PATH = os.getenv("ANCHOR_ABI_PATH", "contracts/EvidenceAnchor.abi.json")
LOOKBACK_BLOCKS = int(os.getenv("ANCHOR_LOOKBACK_BLOCKS", "1000"))

# Minimal ABI fallback if file not provided.
# Matches: function anchorEvidence(bytes32 bundleHash)
#          event EvidenceAnchored(bytes32 bundleHash, address sender, uint256 ts)
FALLBACK_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "internalType": "bytes32", "name": "bundleHash", "type": "bytes32"},
            {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "ts", "type": "uint256"},
        ],
        "name": "EvidenceAnchored",
        "type": "event",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "bundleHash", "type": "bytes32"}],
        "name": "anchorEvidence",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


_w3: Optional[Web3] = None
_contract: Optional[Contract] = None
_acct = None


def _hex32_from_prefixed(hex_str: str) -> bytes:
    if not isinstance(hex_str, str) or not hex_str.startswith("0x"):
        raise ValueError("bundle_hash must be 0x-prefixed hex string")
    hex_body = hex_str[2:]
    if len(hex_body) != 64:
        raise ValueError("bundle_hash must be 32-byte (64 hex chars)")
    return int(hex_body, 16).to_bytes(32, "big")


def _load_web3() -> Web3:
    global _w3
    if _w3 is None:
        _w3 = Web3(Web3.HTTPProvider(FLARE_RPC))
    return _w3


def _load_contract() -> Tuple[Web3, Contract]:
    global _contract, _acct
    w3 = _load_web3()

    # Load ABI
    abi: List[Dict[str, Any]]
    if ABI_PATH and Path(ABI_PATH).exists():
        import json

        abi = json.loads(Path(ABI_PATH).read_text())
    else:
        abi = FALLBACK_ABI

    if not CONTRACT_ADDR:
        raise RuntimeError("ANCHOR_CONTRACT_ADDR is not set")

    address = to_checksum_address(CONTRACT_ADDR)
    contract = w3.eth.contract(address=address, abi=abi)

    # Private key may be missing for read-only operations
    if PRIVATE_KEY:
        _acct = w3.eth.account.from_key(PRIVATE_KEY)

    _contract = contract
    return w3, contract


def _estimate_fees_eip1559(w3: Web3) -> Optional[Tuple[int, int]]:
    try:
        # Use fee_history to derive a reasonable tip
        history = w3.eth.fee_history(5, "latest", [10, 50, 90])
        base_fees = history["baseFeePerGas"]
        base = int(base_fees[-1])
        # Pick a conservative tip (2 gwei) or max priority from history
        tip = int(2e9)
        try:
            prio = history.get("reward", [])
            if prio and prio[-1]:
                # Use median (50th percentile)
                tip = max(tip, int(prio[-1][1]))
        except Exception:
            pass
        max_priority = tip
        # Max fee = base * 2 + tip (simple rule)
        max_fee = base * 2 + max_priority
        return max_fee, max_priority
    except Exception:
        return None


def _build_tx_anchor(
    w3: Web3, contract: Contract, from_addr: str, bundle_hash32: bytes
) -> Dict[str, Any]:
    func = contract.functions.anchorEvidence(bundle_hash32)
    # Start with a basic tx skeleton
    tx: Dict[str, Any] = {
        "from": from_addr,
        "nonce": w3.eth.get_transaction_count(from_addr, "pending"),
        "chainId": w3.eth.chain_id,
    }

    # Try EIP-1559
    fees = _estimate_fees_eip1559(w3)
    if fees:
        max_fee, max_priority = fees
        tx.update({"type": 2, "maxFeePerGas": max_fee, "maxPriorityFeePerGas": max_priority})
    else:
        # Fallback to legacy
        tx.update({"gasPrice": w3.eth.gas_price})

    # Gas estimate
    try:
        gas_est = func.estimate_gas({"from": from_addr})
        # Add a safety margin
        gas_est = int(gas_est * 1.2)
    except Exception:
        # Fallback fixed gas
        gas_est = 200_000

    tx.update({"gas": gas_est})

    built = func.build_transaction(tx)
    return built


def anchor_bundle(bundle_hash_hex: str) -> Tuple[str, int]:
    """
    Anchors the 32-byte bundle hash on-chain by calling anchorEvidence.
    Returns (txid_hex, blockNumber) after waiting for 1 confirmation.
    """
    if not PRIVATE_KEY:
        raise RuntimeError("ANCHOR_PRIVATE_KEY is not set")

    w3, contract = _load_contract()
    acct = w3.eth.account.from_key(PRIVATE_KEY)
    from_addr = acct.address

    bundle_hash32 = _hex32_from_prefixed(bundle_hash_hex)

    # Retry loop for nonce/gas issues
    last_err = None
    for attempt in range(3):
        try:
            tx = _build_tx_anchor(w3, contract, from_addr, bundle_hash32)
            signed = acct.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
            if receipt and receipt.get("status", 1) == 1:
                return tx_hash.hex(), receipt["blockNumber"]
            last_err = RuntimeError("Transaction failed with status != 1")
        except Exception as e:
            last_err = e
            # Small backoff and nonce bump
            time.sleep(1 + attempt)
    if last_err:
        raise last_err  # propagate last error
    raise RuntimeError("Unknown error anchoring bundle")


def find_anchor(bundle_hash_hex: str) -> ChainMatch:
    """
    Attempts to find the EvidenceAnchored event for the given bundle hash.
    Returns ChainMatch(matches, txid?, anchored_at?).
    Strategy:
      - Query logs for the EvidenceAnchored event from latest-LOOKBACK to latest.
      - Decode logs and compare bundleHash (in data) to provided hash.
      - Return the first match with txid and block timestamp.
    Works whether or not bundleHash is indexed (topics) due to decoding step.
    """
    logger.debug("VERIFY checking: %s", bundle_hash_hex)
    logger.debug("contract=%s", CONTRACT_ADDR)
    print(f"DEBUG: VERIFY checking: {bundle_hash_hex}")
    print(f"DEBUG: contract={CONTRACT_ADDR}")
    
    try:
        w3, contract = _load_contract()
        print(f"DEBUG: Contract loaded successfully")
    except Exception as e:
        logger.debug("Failed to load contract: %s", str(e))
        print(f"DEBUG: Failed to load contract: {str(e)}")
        # Read-only without contract address is not possible
        return ChainMatch(matches=False)

    try:
        bundle_hash32 = _hex32_from_prefixed(bundle_hash_hex)
        logger.debug("bundle_hash32: %s", bundle_hash32.hex())
        print(f"DEBUG: bundle_hash32: {bundle_hash32.hex()}")
    except Exception as e:
        logger.debug("Failed to convert hash: %s", str(e))
        print(f"DEBUG: Failed to convert hash: {str(e)}")
        return ChainMatch(matches=False)

    latest = w3.eth.block_number
    address = to_checksum_address(CONTRACT_ADDR)  # type: ignore
    print(f"DEBUG: Latest block: {latest}, address={address}")

    # Build event signature topic for filtering (first topic)
    event_abi = None
    for item in contract.abi:  # type: ignore
        if item.get("type") == "event" and item.get("name") == "EvidenceAnchored":
            event_abi = item
            break

    if event_abi is None:
        # Without ABI, cannot decode; bail
        return ChainMatch(matches=False)

    # Calculate event topic manually since _get_event_topic() returns None
    from eth_utils import keccak
    event_signature = "EvidenceAnchored(bytes32,address,uint256)"
    event_topic = keccak(text=event_signature)
    
    logger.debug("topic0=%s", event_topic.hex())
    print(f"DEBUG: topic0={event_topic.hex()}")
    
    # Search in chunks due to RPC provider limit of 30 blocks
    chunk_size = 25  # Use 25 to be safe
    all_logs = []
    
    # Start from recent blocks and work backwards
    current_to = latest
    while current_to > 0:
        current_from = max(0, current_to - chunk_size)
        print(f"DEBUG: Searching chunk {current_from} to {current_to}")
        
        try:
            chunk_logs = w3.eth.get_logs(
                {
                    "fromBlock": current_from,
                    "toBlock": current_to,
                    "address": address,
                    "topics": [event_topic],
                }
            )
            all_logs.extend(chunk_logs)
            print(f"DEBUG: Found {len(chunk_logs)} logs in chunk")
            
            # If we found logs, we can stop searching (newest first)
            if chunk_logs:
                break
                
        except Exception as e:
            print(f"DEBUG: Chunk search failed: {str(e)}")
            break
            
        current_to = current_from - 1
        if current_to <= 0:
            break
    
    logs = all_logs
    logger.debug("Found %s total logs", len(logs))
    print(f"DEBUG: Found {len(logs)} total logs")

    # Iterate newest-first for speed
    for i, log in enumerate(reversed(logs)):
        try:
            logger.debug("Processing log %s: tx=%s, block=%s", i, log["transactionHash"].hex(), log["blockNumber"])
            print(f"DEBUG: Processing log {i}: tx={log['transactionHash'].hex()}, block={log['blockNumber']}")
            
            # Since bundleHash is not indexed, it's in the data field
            # Data format: bundleHash (32 bytes) + ts (32 bytes)
            if len(log.data) >= 32:
                ev_hash_bytes = log.data[:32]
                logger.debug("Log %s bundleHash from data: %s", i, ev_hash_bytes.hex())
                print(f"DEBUG: Log {i} bundleHash from data: {ev_hash_bytes.hex()}")
                
                if ev_hash_bytes == bundle_hash32:
                    tx_hash = log["transactionHash"].hex()
                    try:
                        blk = w3.eth.get_block(log["blockNumber"])
                        ts = blk.get("timestamp")
                        anchored_at = datetime.fromtimestamp(ts, tz=timezone.utc) if isinstance(ts, int) else None
                    except Exception as e:
                        print(f"DEBUG: Failed to get block timestamp: {str(e)}")
                        # Use current time as fallback
                        anchored_at = datetime.now(timezone.utc)
                    
                    logger.debug("MATCH FOUND: tx=%s, block=%s, time=%s", tx_hash, log["blockNumber"], anchored_at)
                    print(f"DEBUG: MATCH FOUND: tx={tx_hash}, block={log['blockNumber']}, time={anchored_at}")
                    return ChainMatch(matches=True, txid=tx_hash, anchored_at=anchored_at)
                else:
                    logger.debug("Log %s hash mismatch: %s != %s", i, ev_hash_bytes.hex(), bundle_hash32.hex())
                    print(f"DEBUG: Log {i} hash mismatch: {ev_hash_bytes.hex()} != {bundle_hash32.hex()}")
            else:
                logger.debug("Log %s data too short: %s bytes", i, len(log.data))
                print(f"DEBUG: Log {i} data too short: {len(log.data)} bytes")
                
        except Exception as e:
            logger.debug("Failed to process log %s: %s", i, str(e))
            print(f"DEBUG: Failed to process log {i}: {str(e)}")
            # Ignore decode issues and continue
            continue

    logger.debug("No matching logs found")
    return ChainMatch(matches=False)
