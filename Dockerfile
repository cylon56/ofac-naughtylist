FROM python:3.11-slim

WORKDIR /app

# Install git for pushing updates
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user. The cron script clones into a fresh temp
# directory under /tmp and writes all output there, so it needs no write
# access to /app.
RUN useradd --create-home --uid 10001 naughtylist
USER naughtylist

# Default: run the pipeline and push results
CMD ["python", "scripts/railway_cron.py"]
