# 🐐 GoatOS - Farm Management System

GoatOS is an open-source farm management platform designed for goat herds. Optimized for barn use with a mobile-friendly **Dark Mode**, it tracks animal health, pedigrees, weight, and milk production. Features include medical records with dosage calculators, a sales ledger, satellite grazing maps, and real-time weather. Built on **Python/Django** and **Docker**, GoatOS provides a secure, all-in-one dashboard for modern herd management.

---

## 🚀 Key Features

### 📊 Dashboard & Analytics
- **At-a-Glance Stats:** Real-time herd counts, active sales, and task reminders.
- **Weather Widget:** Integrated Open-Meteo API for real-time farm weather conditions (no API key required).
- **Dark Mode:** Fully responsive UI with a toggleable Dark Mode for low-light barn checks.

### 🐐 Herd Management
- **Individual Profiles:** Track age, breed, bio, and status (Healthy, Sick, At Vet, Deceased).
- **Pedigree Tracking:** Visual lineage trees linking Sires and Dams.
- **Photo Gallery:** Upload and manage photos for each animal.
- **QR/Stall Cards:** Generate printable stall cards with identifying info.

### 🏥 Health & Tools
- **Medical Records:** Log vaccinations, deworming, and illness.
- **Dosage Calculator:** Built-in calculator to determine medication volume based on animal weight and dosage rate.
- **Weight Tracking:** Log weights and visualize growth over time with interactive charts.
- **Gestation Calculator:** Estimate kidding dates based on breeding logs.

### 🥛 Production & Sales
- **Milk Log:** Track daily yields and visualize production trends.
- **Sales Ledger:** Record sales, deposits, and payment statuses (Pending vs. Paid).
- **Grazing Map:** Satellite view integration (Google Maps) to draw and manage grazing zones.

---

## 🛠 Tech Stack

- **Backend:** Python 3.11, Django 4.2
- **Frontend:** HTML5, CSS3 (Bootstrap-ish styling), JavaScript
- **Database:** SQLite (Default, easily swappable for Postgres)
- **Charts:** Chart.js
- **Containerization:** Docker & Docker Compose

---

## 🐳 Docker Installation (Recommended)

GoatOS is designed to run in a containerized environment.

### ✅ Prerequisites
- Docker
- Docker Compose

### 1) Clone & Build
```bash
git clone https://github.com/yourusername/goatos.git
cd goatos
docker-compose build
```

### 2) Run the Container

#### Option A: Docker Compose (Cross-Platform)
The standard way to run anywhere:
```bash
docker-compose up -d
```

#### Option B: Helper Scripts (Quick Reset)
- **Linux/Mac:** Run `./rebuild.sh`
- **Windows:** Run `rebuild.bat`

The application will launch on port **4321** with **SSL enabled** (via `django-sslserver`) to support secure features like camera access on mobile devices.

### 3) Access
Open your browser and navigate to:
```txt
https://localhost:4321
# OR
https://YOUR_SERVER_IP:4321
```

> **Note:** The Docker container includes a startup script that automatically handles database migrations.  
> If you need to reset the database, simply delete the `db.sqlite3` file on your host machine and restart the container.

---

## 💻 Manual Installation (Local Dev)

If you prefer to run without Docker:

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Apply Migrations
```bash
python manage.py migrate
```

### Create Admin User
```bash
python manage.py createsuperuser
```

### Run Server
```bash
python manage.py runsslserver 0.0.0.0:4321
```

---

## ⚙️ Configuration

You can configure the application via the Admin Panel (`/admin/`) or by setting environment variables in `docker-compose.yml`.

### Key Settings
- **Farm Settings:** Set your Farm Name, Latitude, and Longitude in the Admin panel to calibrate the Weather widget and Map center.
- **Google Maps API:** Add your API key in Farm Settings to enable the Grazing Map and Location Picker.

---

## 🔧 Troubleshooting

### Forgot Admin Password?
Since GoatOS runs in a Docker container, you can reset credentials directly from the command line without needing email recovery.

#### Option 1: Reset password for an existing user
Replace `admin` with your actual username:
```bash
docker exec -it goatos-container python manage.py changepassword admin
```

#### Option 2: Create a new admin user
If you forgot the username entirely, create a brand new superuser account:
```bash
docker exec -it goatos-container python manage.py createsuperuser
```

> *(Note: If your container is named differently, use `docker ps` to find the correct name and replace `goatos-container`.)*

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
