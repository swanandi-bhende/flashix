DEV SETUP
=========

Prerequisites
-------------
- Node.js 18.0+
- Python 3.10+
- Git 2.30+
- Docker 20.10+ (optional)

Clone & Navigate
-----------------
```
git clone https://github.com/your-org/flashix-arbitrage.git
cd flashix-arbitrage
```

Install Dependencies
--------------------
Python (backend/agent/compute):
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Node (mempool listener & scripts):
```
npm install
```

Configure Environment
---------------------
```
cp .env.example .env.local
# open .env.local in your editor and fill keys
```
Where to obtain keys:
- 0G RPC: 0G docs
- Gemini API: Google Cloud console
- Mempool provider: Bloxroute / private relay portal

Verify Installation
-------------------
```
python -m pytest tests/unit/ --tb=short
npm run lint
python compute/inference_validator.py --test
node mempool-listener/ingester.js --dry-run
```

Run the Application
-------------------
```
./scripts/start_agent.sh
npm run mempool:listen
```

Troubleshooting
---------------
- If `ModuleNotFoundError` for `langchain`, ensure venv is activated and `pip install -r requirements.txt` succeeded.
- If mempool WebSocket fails, verify `MEMPOOL_WEBSOCKET_URL` and provider credentials.

Startup Order Diagram
- Start mempool listener
- Start compute validator (optional)
- Start agent
- Monitor logs/metrics
