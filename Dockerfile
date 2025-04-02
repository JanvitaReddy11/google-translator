FROM python:3.9-slim

WORKDIR /app

# Install system dependencies required by PyAudio
RUN apt-get update && apt-get install -y \
    build-essential \
    portaudio19-dev \
    python3-pyaudio \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for static files
RUN mkdir -p /tmp/static/audio /tmp/static/transcripts

# The port that the container will listen on
ENV PORT=8080
ENV STATIC_DIR=/tmp/static

# Run the application
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}