#!/bin/bash

echo "🚀 Starting SmartSearch AI Backend..."

# Load environment variables
export $(cat ../.env | grep -v '^#' | xargs)

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start FastAPI server
echo "✅ Starting API server on http://localhost:8000"
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
