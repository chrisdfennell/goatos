@echo off
echo 🐐 --- GoatOS Automation Script (Windows) ---

echo 🛑 Stopping existing container...
docker stop goatos_app 2>NUL
docker rm goatos_app 2>NUL

echo 🔨 Building Docker image...
docker build -t goatos:latest .

echo 🚀 Starting new container...
:: Required env vars for production:
::   SECRET_KEY      - A strong random string
::   ALLOWED_HOSTS   - Comma-separated hostnames, e.g. "goatos.example.com,192.168.1.50"
::   DEBUG           - Set to "True" only for development (defaults to False)
docker run -d --name goatos_app --network sso-network -p 4321:4321 -e DEBUG=True -e ALLOWED_HOSTS=localhost,127.0.0.1,%COMPUTERNAME% -v "%cd%:/app" goatos:latest

:: Note: Migrations are now handled automatically by the Dockerfile CMD,
:: but we can force output here if needed.
echo 📦 Checking Database Status...
docker exec goatos_app python manage.py showmigrations

echo ✅ Success! GoatOS is running.
echo 🔗 Access at: https://localhost:4321
echo.
echo 📝 First time? Create an admin user:
echo    docker exec -it goatos_app python manage.py createsuperuser
pause