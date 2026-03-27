FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r api/requirements.txt

# Copy application code
COPY api/ ./api/
COPY tools/ ./tools/
COPY generator/ ./generator/
COPY publisher/ ./publisher/
COPY publishers/ ./publishers/
COPY orchestrator.py run.py ./

# Create output directory
RUN mkdir -p output

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
