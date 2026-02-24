#!/bin/bash

echo "🐐 --- GoatOS Rebuild Script ---"

# 1. Stop and remove existing containers
echo "🛑 Stopping existing containers..."
docker-compose down

# 2. Rebuild and start
echo "🔨 Building and starting containers..."
docker-compose up -d --build

if [ $? -ne 0 ]; then
    echo "❌ Build failed. Aborting."
    exit 1
fi

# 3. Check migration status
echo "📦 Checking Database Status..."
docker-compose exec goatos python manage.py showmigrations

echo "✅ Success! GoatOS is running."
echo "🔗 Access at: https://$(hostname):4321"
