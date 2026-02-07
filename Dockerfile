FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# libgl1/libglib2.0-0/libsm6/libxext6/libxrender1 are for OpenCV
# libgomp1 is for PaddlePaddle/PaddleOCR
# build-essential for compiling any missing wheels
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies clearly
COPY requirements.txt .

# Install requirements, but force uninstall opencv-python afterwards to be safe, then install headless
RUN pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y opencv-python && \
    pip install opencv-python-headless>=4.9.0

# Copy application code
COPY . .

# Set environment variables
ENV PORT=8000
ENV HOST=0.0.0.0

# Start command
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
