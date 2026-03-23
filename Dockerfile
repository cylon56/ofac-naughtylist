FROM python:3.11-slim

WORKDIR /app

# Install git for pushing updates
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: run the pipeline and push results
CMD ["python", "scripts/railway_cron.py"]
