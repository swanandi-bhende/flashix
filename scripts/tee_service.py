"""
Simple TEE signing and persistence service for demo purposes.
Run with: python3 scripts/tee_service.py

Provides endpoints:
- POST /api/tee/sign  -> expects JSON artifact, returns a structured proof { signature, algorithm, signerIdentity, publicKey, signedAt, verificationSteps, url }
- POST /api/traces/persist -> expects JSON { artifact, receipt } and persists to disk returning { url }

This is a minimal demo server and NOT a production TEE.
"""
from flask import Flask, request, jsonify
import os
import json
from pathlib import Path
import time
import hashlib
import hmac

# reuse TEESigner if available
try:
    from compute.tee_signer import TEESigner
    signer = TEESigner()
except Exception as e:
    signer = None

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data' / 'public'
SIGNED_DIR = DATA_DIR / 'signed'
TRACES_DIR = DATA_DIR / 'traces'
SIGNED_DIR.mkdir(parents=True, exist_ok=True)
TRACES_DIR.mkdir(parents=True, exist_ok=True)

@app.route('/api/tee/sign', methods=['POST'])
def sign():
    payload = request.get_json() or {}
    request_id = payload.get('requestId') or payload.get('id') or f"req-{int(time.time())}"
    # canonicalize artifact
    artifact = json.dumps(payload, sort_keys=True)
    signature = None
    algorithm = 'secp256k1-keccak256'
    signer_identity = os.getenv('TEE_SIGNER_ADDRESS', 'demo-tee-signer')
    public_key = os.getenv('TEE_SIGNER_PUBLIC_KEY', signer_identity)
    verification_steps = [
        'Canonicalize artifact JSON',
        'Hash payload with keccak256',
        'Sign hash in TEE boundary or demo signer',
        'Persist proof JSON to disk',
    ]
    if signer:
        try:
            # signer.sign_output expects an object with attributes; for demo pass dict
            class Dummy: pass
            d = Dummy()
            # map fields used by signer if present
            d.opportunity_id = payload.get('sourceOpportunityId') or payload.get('opportunityId')
            d.expected_profit_usdc = payload.get('payload', {}).get('expectedProfit') or payload.get('expectedProfit') or 0
            d.borrow_amount = 0
            d.collateral_required = 0
            d.expiry_timestamp = int(time.time()) + 3600
            signature = signer.sign_output(d)
        except Exception as e:
            signature = None
    # fallback signature is sha256 prefix
    if not signature:
        algorithm = 'hmac-sha256-demo'
        hmac_key = os.getenv('TEE_PROOF_HMAC_KEY', os.getenv('TEE_SIGNING_KEY', 'demo-proof-key'))
        signature = hmac.new(hmac_key.encode('utf-8'), artifact.encode('utf-8'), hashlib.sha256).hexdigest()
    filename = SIGNED_DIR / f"signed-{request_id}-{int(time.time())}.json"
    signed_at = int(time.time())
    proof = {
        'requestId': request_id,
        'algorithm': algorithm,
        'signerIdentity': signer_identity,
        'publicKey': public_key,
        'signedAt': signed_at,
        'signature': signature,
        'verificationSteps': verification_steps,
        'artifact': payload,
    }
    with filename.open('w', encoding='utf-8') as f:
        f.write(json.dumps(proof, sort_keys=True))
    url = f"/data/public/signed/{filename.name}"
    return jsonify({
        'signature': signature,
        'algorithm': algorithm,
        'signerIdentity': signer_identity,
        'publicKey': public_key,
        'signedAt': signed_at,
        'verificationSteps': verification_steps,
        'url': url,
        'proof': proof,
    })

@app.route('/api/traces/persist', methods=['POST'])
def persist():
    payload = request.get_json() or {}
    request_id = payload.get('requestId') or f"t-{int(time.time())}"
    filename = TRACES_DIR / f"trace-{request_id}-{int(time.time())}.json"
    with filename.open('w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    url = f"/data/public/traces/{filename.name}"
    return jsonify({'url': url})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
