FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cache-bust: added livekit-plugins-openai for Mercury 2)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# LiveKit agents CLI entry point
# 'start' runs in production mode (vs 'dev' for development)
CMD ["python", "-m", "agent.main", "start"]
