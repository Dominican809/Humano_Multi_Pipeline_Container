FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    imapclient \
    requests \
    requests-toolbelt \
    pandas \
    openpyxl \
    loguru \
    python-dotenv \
    openai \
    numpy \
    tqdm \
    resend

# Copy the email watcher files
COPY pipeline_watcher.py run_pipeline.sh health_check.py ./

# Copy the emisor_goval module (needed for the pipeline)
COPY ../emisor_goval ./emisor_goval

# Copy other necessary files
COPY ../main.py ./
COPY ../requirements.txt ./
COPY ../.env ./

# Make scripts executable
RUN chmod +x /app/run_pipeline.sh /app/health_check.py

# Create necessary directories
RUN mkdir -p /app/logs /app/data

# Create volume for persistent state
VOLUME ["/state"]

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('/state/processed.sqlite3')" || exit 1

# Run the email watcher
CMD ["python", "/app/pipeline_watcher.py"]
