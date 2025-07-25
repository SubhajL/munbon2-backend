FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for spatial libraries
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Set environment variables
ENV PYTHONPATH=/app/src
ENV SERVICE_PORT=3023

# Expose port
EXPOSE 3023

# Run the application
CMD ["python", "src/main.py"]