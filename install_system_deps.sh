#!/bin/bash

# Update package lists
apt-get update

# Install Tesseract OCR and language data
apt-get install -y tesseract-ocr
apt-get install -y tesseract-ocr-ara tesseract-ocr-eng

# Install development libraries
apt-get install -y \
    build-essential \
    python3-dev \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev

# Install PDF processing tools
apt-get install -y \
    poppler-utils \
    ghostscript \
    libmagickwand-dev

# Install additional dependencies
apt-get install -y \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0

# Create necessary directories
mkdir -p media/documents
mkdir -p temp
mkdir -p logs

# Set permissions
chmod 755 media
chmod 755 temp
chmod 755 logs

# Clean up
apt-get clean
rm -rf /var/lib/apt/lists/*

echo "System dependencies installation completed successfully!" 