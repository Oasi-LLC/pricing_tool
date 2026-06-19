#!/bin/bash
# Morning data pipeline — activates venv, then runs pl_daily + nightly pull + rules push.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "venv/bin/activate" ]]; then
    echo "❌ Virtual environment not found at $ROOT/venv"
    echo "   Create it with: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

echo "🔄 Activating virtual environment..."
source venv/bin/activate

echo "🚀 Starting morning data pipeline..."
python scripts/run_morning_data_pipeline.py "$@"
