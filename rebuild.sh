#!/bin/bash

# --- Configuration ---
CONTAINER_NAME="goatos-container"
IMAGE_NAME="goatos"
PORT="4321"
PROJECT_DIR=$(pwd)

echo "🐐 --- GoatOS Automation Script ---"

# 1. Stop and remove the existing container
echo "🛑 Stopping existing container..."
docker stop $CONTAINER_NAME 2>/dev/null
docker rm $CONTAINER_NAME 2>/dev/null

# Wait for Docker to release the port
sleep 3

# 2. Rebuild the Docker Image
echo "🔨 Building Docker image..."
docker build -t $IMAGE_NAME .

if [ $? -ne 0 ]; then
    echo "❌ Build failed. Aborting."
    exit 1
fi

# 3. Run the new Container
echo "🚀 Starting new container..."
docker run -d \
  --name $CONTAINER_NAME \
  --restart unless-stopped \
  -p $PORT:$PORT \
  -v "$PROJECT_DIR":/app \
  $IMAGE_NAME

# 4. AUTOMATIC MIGRATIONS (The Magic Step)
echo "📦 Running Database Migrations..."
# We use 'docker exec' to run the python commands INSIDE the running container
docker exec $CONTAINER_NAME python manage.py makemigrations
docker exec $CONTAINER_NAME python manage.py migrate

echo "✅ Success! GoatOS is running."
echo "🔗 Access at: https://$(hostname):$PORT"