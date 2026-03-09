FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (Pillow + nginx + supervisor)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Collect static files at build time
RUN SECRET_KEY=build-placeholder python manage.py collectstatic --noinput

# Configure nginx — run as root so it can read volume-mounted media files
RUN rm -f /etc/nginx/sites-enabled/default && \
    sed -i 's/^user .*/user root;/' /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/conf.d/goatos.conf

# Configure supervisor
COPY supervisord.conf /etc/supervisord.conf

# Fix line endings (Windows CRLF -> Unix LF) and make entrypoint executable
RUN sed -i 's/\r$//' /app/entrypoint.sh /etc/supervisord.conf /etc/nginx/conf.d/goatos.conf && \
    chmod +x /app/entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
