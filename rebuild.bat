@echo off
echo 🐐 --- GoatOS Rebuild Script (Windows) ---

echo 🛑 Stopping existing containers...
docker-compose down

echo 🔨 Building and starting containers...
docker-compose up -d --build

echo 📦 Checking Database Status...
docker-compose exec goatos python manage.py showmigrations

echo ✅ Success! GoatOS is running.
echo 🔗 Access at: https://localhost:4321
pause
