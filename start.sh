#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Create virtualenv if missing
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
  venv/bin/pip install -r requirements.txt
fi

# Create required directories
mkdir -p uploads sample_outputs

echo ""
echo "==================================================="
echo "  MEP AI Compliance System"
echo "==================================================="
echo ""
echo "  API docs:  http://localhost:8001/docs"
echo "  Upload:    POST http://localhost:8001/upload/"
echo "  Report:    GET  http://localhost:8001/compliance/report?filename=<name>"
echo ""
echo "  Quick test:"
echo "    curl -X POST http://localhost:8001/upload/ -F 'file=@sample_inputs/hvac_spec.txt'"
echo "    curl 'http://localhost:8001/compliance/report?filename=hvac_spec.txt'"
echo ""
echo "  Set ANTHROPIC_API_KEY for real AI explanations:"
echo "    export ANTHROPIC_API_KEY=sk-ant-api03-..."
echo ""
echo "==================================================="
echo ""

venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
