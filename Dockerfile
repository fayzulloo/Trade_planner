# Python base image
FROM python:3.11-slim

# System package lar (Tesseract + clean)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-rus \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Work directory
WORKDIR /app

# Fayllarni copy qilish
COPY . .

# Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Environment (optional)
ENV PYTHONUNBUFFERED=1

# Botni ishga tushirish
CMD ["python", "main.py"]