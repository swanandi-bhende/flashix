#!/usr/bin/env python3
"""
Judge Verification CLI

Reconstructs the canonical message hash for a signal, recovers the signer,
and checks whether it matches the registered TEE address.

Usage:
  python compute/verify_signal.py --signature <sig> --fields '<json>'

The --fields argument must be a JSON object containing:
  opportunity_id, primary_dex, counter_dex, borrow_amount,
  collateral_required, expected_profit_usdc, expiry_timestamp, chain_id
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import keccak

from signal_encoder import SignalEncoder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a Flashix signal signature")
    parser.add_argument("--signature", required=True, help="Hex-encoded signature")
    parser.add_argument("--fields", required=True, help="JSON object with signal fields")
    parser.add_argument("--expected-address", default=None, help="Expected TEE address to compare against")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fields = json.loads(args.fields)

    encoded = SignalEncoder.encode_for_signing(fields)
    message_hash = keccak(encoded)
    recovered = Account.recover_message(encode_defunct(message_hash), signature=args.signature)

    print(f"Canonical message hash: 0x{message_hash.hex()}")
    print(f"Recovered signer address: {recovered}")

    if args.expected_address:
        print(f"Expected TEE address: {args.expected_address}")
        print(f"Match: {recovered.lower() == args.expected_address.lower()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
