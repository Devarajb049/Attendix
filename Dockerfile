FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright chromium browser along with required OS dependencies
RUN playwright install --with-deps chromium

# Copy application files
COPY . .

ENV PYTHONUNBUFFERED=1

# Command to run FastAPI server with Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
