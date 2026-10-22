FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . /app/

# Expose port (Uvicorn signaling service on 8081)
EXPOSE 8081

# Command untuk menjalankan aplikasi (socket_app membungkus FastAPI dan Socket.IO)
CMD ["uvicorn", "app.main:socket_app", "--host", "0.0.0.0", "--port", "8081"]
