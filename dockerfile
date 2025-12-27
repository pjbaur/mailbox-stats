FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only Python files (credentials handled via Secret Manager)
COPY *.py ./

# Create output directory for exports
RUN mkdir -p /tmp/out

ENV PYTHONUNBUFFERED=1

# Run with no args by default - configured via environment variables
# MODE, SAMPLE_SIZE, EXPORT_CSV, OUTPUT_DIR, GCS_BUCKET, SKIP_DB, TOKEN_JSON
ENTRYPOINT ["python", "gmail_stats.py"]
CMD []
