#!/usr/bin/env bash
set -euo pipefail

echo "Running flashix bootstrap..."

req_node_major=18
req_python_major=3
req_python_minor=10

which node >/dev/null || { echo "node not found"; exit 1; }
which python3 >/dev/null || { echo "python3 not found"; exit 1; }

node_major=$(node -v | sed 's/v\([0-9]*\).*/\1/')
if [ "${node_major}" -lt ${req_node_major} ]; then
  echo "Node.js ${req_node_major}+ required. Found: ${node_major}"; exit 1
fi

python_minor=$(python3 -c 'import sys; print("%s.%s"%(sys.version_info.major, sys.version_info.minor))')
if [[ "${python_minor}" < "${req_python_major}.${req_python_minor}" ]]; then
  echo "Python ${req_python_major}.${req_python_minor}+ required. Found: ${python_minor}"; exit 1
fi

echo "Creating virtual env..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt || { echo "pip install failed"; exit 1; }

echo "Installing node dependencies..."
npm install || { echo "npm install failed"; exit 1; }

echo "Prepare directories..."
mkdir -p data logs data/metrics data/replays

if [ ! -f .env.local ]; then
  cp .env.example .env.local
  echo "Copied .env.example to .env.local — edit .env.local to add credentials"
fi

echo "Running unit tests..."
./scripts/run_tests.sh || { echo "Some tests failed"; exit 1; }

echo "Bootstrap complete. Next: edit .env.local and run ./scripts/start_agent.sh"
