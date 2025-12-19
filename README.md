# 🐐 GoatOS - Farm Management System

GoatOS is a comprehensive, open-source farm management platform designed specifically for managing goat herds. It provides an all-in-one dashboard to track animal health, production, sales, and grazing management, optimized for both desktop and mobile use in the barn.

---

## 🚀 Key Features

### 📊 Dashboard & Analytics
- **At-a-Glance Stats:** Real-time herd counts, active sales, and task reminders  
- **Weather Widget:** Integrated Open-Meteo API for real-time farm weather conditions (no API key required)  
- **Dark Mode:** Fully responsive UI with a toggleable Dark Mode for low-light barn checks  

### 🐐 Herd Management
- **Individual Profiles:** Track age, breed, bio, and status (Healthy, Sick, At Vet, Deceased)  
- **Pedigree Tracking:** Visual lineage trees linking Sires and Dams  
- **Photo Gallery:** Upload and manage photos for each animal  
- **QR / Stall Cards:** Generate printable stall cards with identifying info  

### 🏥 Health & Tools
- **Medical Records:** Log vaccinations, deworming, and illness  
- **Dosage Calculator:** Built-in calculator to determine medication volume based on animal weight and dosage rate  
- **Weight Tracking:** Log weights and visualize growth over time with interactive charts  
- **Gestation Calculator:** Estimate kidding dates based on breeding logs  

### 🥛 Production & Sales
- **Milk Log:** Track daily yields and visualize production trends  
- **Sales Ledger:** Record sales, deposits, and payment statuses (Pending vs. Paid)  
- **Grazing Map:** Satellite view integration (Google Maps) to draw and manage grazing zones  

---

## 🛠 Tech Stack

- **Backend:** Python 3.11, Django 4.2  
- **Frontend:** HTML5, CSS3 (Bootstrap-style), JavaScript  
- **Database:** SQLite (default, easily swappable for PostgreSQL)  
- **Charts:** Chart.js  
- **Containerization:** Docker & Docker Compose  

---

## 🐳 Docker Installation (Recommended)

GoatOS is designed to run in a containerized environment.

### Prerequisites
- Docker  
- Docker Compose  

### 1. Clone & Build
```bash
git clone https://github.com/yourusername/goatos.git
cd goatos
docker-compose build
```

### 2. Run the Container
```bash
docker-compose up -d
```

The application will launch on **port 4321** with SSL enabled (via `django-sslserver`) to support secure features like camera access on mobile devices.

### 3. Access
```text
https://localhost:4321
# OR
https://YOUR_SERVER_IP:4321
```

> **Note:**  
> The Docker container includes a startup script that automatically handles database migrations.  
> To reset the database, delete the `db.sqlite3` file on the host machine and restart the container.

---

## 💻 Manual Installation (Local Development)

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

### Run Development Server (SSL)
```bash
python manage.py runsslserver 0.0.0.0:4321
```

---

## ⚙️ Configuration

Configuration can be managed via the **Admin Panel** (`/admin/`) or environment variables in `docker-compose.yml`.

### Key Settings
- **Farm Settings:** Set Farm Name, Latitude, and Longitude in the Admin panel to calibrate:
  - Weather widget
  - Map center
- **Google Maps API:** Add your API key in Farm Settings to enable:
  - Grazing Map
  - Location picker

---

## 🤝 Contributing

Contributions are welcome!  
Feel free to submit a Pull Request, open an issue, or suggest improvements.

---

🐐 **Happy Herding with GoatOS!**
