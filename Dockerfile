# Multi-stage / clean Python 3.11-slim container for Live ETA System
FROM python:3.11-slim

# Set environment variables for clean container output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    HOST=0.0.0.0 \
    PORT=5000

# Set working directory
WORKDIR /app

# Install system dependencies if required (sqlite3 & build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies first (cached layer)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . /app/

# Expose web service port
EXPOSE 5000

# Health check to ensure service is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/dashboard || exit 1

# Start container with Gunicorn production server (or python app.py)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
