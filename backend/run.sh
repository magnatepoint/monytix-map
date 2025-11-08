#!/bin/bash

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Start Redis
redis-server --daemonize yes

# Start Celery Worker
celery -A celery_app worker --loglevel=info --concurrency=4 &

# Start FastAPI Server
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

