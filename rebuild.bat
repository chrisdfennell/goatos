@echo off
echo 🐐 --- GoatOS Automation Script (Windows) ---

echo 🛑 Stopping existing container...
docker stop goatos_app 2>NUL
docker rm goatos_app 2>NUL

echo 🔨 Building Docker image...
docker build -t goatos:latest .

echo 🚀 Starting new container...
:: Mounts the current directory (%cd%) to /app so code changes reflect instantly
docker run -d --name goatos_app -p 4321:4321 -v "%cd%:/app" goatos:latest

:: Note: Migrations are now handled automatically by the Dockerfile CMD,
:: but we can force output here if needed.
echo 📦 Checking Database Status...
docker exec goatos_app python manage.py showmigrations

echo ✅ Success! GoatOS is running.
echo 🔗 Access at: https://localhost:4321
pause