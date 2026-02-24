#!/bin/bash

echo "🐐 --- GoatOS Rebuild Script ---"

# Detect docker compose command (v2 "docker compose" vs v1 "docker-compose")
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif docker-compose version >/dev/null 2>&1; then
    DC="docker-compose"
else
    echo "❌ Neither 'docker compose' nor 'docker-compose' found. Install Docker Compose first."
    exit 1
fi

# 1. Stop and remove existing containers
echo "🛑 Stopping existing containers..."
$DC down

# 2. Rebuild and start
echo "🔨 Building and starting containers..."
$DC up -d --build

if [ $? -ne 0 ]; then
    echo "❌ Build failed. Aborting."
    exit 1
fi

# 3. Check migration status
echo "📦 Checking Database Status..."
$DC exec goatos python manage.py showmigrations

echo "✅ Success! GoatOS is running."
echo "🔗 Access at: https://$(hostname):4321"
