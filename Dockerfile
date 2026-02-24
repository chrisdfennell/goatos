# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
# Added gcc here just in case other packages need compilation, 
# along with your requested libjpeg/zlib for Pillow.
RUN apt-get update && apt-get install -y \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy project
COPY . /app/

# Expose the port Django runs on
EXPOSE 4321

# Run the application
# FIX: Using "sh -c" allows us to run multiple commands.
# 1. migrate --fake-initial: Skips table creation if tables already exist (prevents crashes).
# 2. runsslserver: Starts your server on port 4321.
CMD ["sh", "-c", "python manage.py migrate --fake-initial && python manage.py runsslserver 0.0.0.0:4321"]