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

# Create necessary directories first
RUN mkdir -p /app/logs /app/data /app/Exceles /tmp /app/shared

# Copy all components
COPY email_watcher/ ./
COPY pipeline_manager.py ./
COPY shared/ ./shared/
COPY shared/error_handler.py ./error_handler.py
COPY viajeros_pipeline/ ./viajeros_pipeline/
COPY si_pipeline/ ./si_pipeline/
COPY config/ ./config/
COPY manual_email_processor.py ./

# Make scripts executable
RUN chmod +x /app/health_check.py
RUN chmod +x /app/manual_email_processor.py

# Create volume for persistent state
VOLUME ["/state"]

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV AUTOMATED_MODE=true

# Health check
HEALTHCHECK --interval=60s --timeout=30s --retries=3 --start-period=60s \
    CMD python /app/health_check.py

# Run the email watcher
CMD ["python", "/app/pipeline_watcher.py"]
