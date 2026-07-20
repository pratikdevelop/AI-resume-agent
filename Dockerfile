# Dockerfile
# Single image used by all agents — entrypoint differs per service

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PyMuPDF
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code
COPY . .

# Default port (overridden per service in docker-compose)
EXPOSE 8000

# Default command (overridden per service in docker-compose)
CMD ["uvicorn", "orchestrator:app", "--host", "0.0.0.0", "--port", "8000"]