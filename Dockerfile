FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway provides $PORT)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

# Create startup script
RUN echo '#!/bin/sh\nuvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}' > /app/start.sh && \
    chmod +x /app/start.sh

# Start FastAPI with uvicorn
CMD ["/bin/sh", "/app/start.sh"]
