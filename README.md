# SIWES Logbook Automation System

![Project Banner](docs/screenshots/student_dashboard.png)

An offline-first, location-verified digital logbook platform for Student Industrial Work Experience Scheme (SIWES) management, built with FastHTML and Faststrap for Anchor University Computer Science students.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Contributing](#contributing)

---

## Overview

The **SIWES Logbook Automation System** is a comprehensive solution for managing the Student Industrial Work Experience Scheme (SIWES) program. It addresses three critical challenges in industrial training management:

### 1. The Verification Gap (Geographical Accountability)

**Problem**: Supervisors cannot verify if students are actually at their workplace, leading to "ghosting" or "back-filling" of logs from home.

**Solution**: **Geofencing** captures GPS coordinates at the moment of entry, ensuring data is only valid if the student is physically within the company's designated radius.

### 2. Administrative Latency (Communication Bottlenecks)

**Problem**: Traditional paper logbooks create a "black hole" where supervisors have zero visibility into student progress for months.

**Solution**: **Real-time Chat and Video Consultation** eliminate wait time between student queries and supervisor responses, allowing immediate intervention.

### 3. Network Instability and Data Loss (The "Offline" Problem)

**Problem**: Standard web applications fail in remote industrial sites with poor network coverage, forcing students to revert to paper.

**Solution**: **Progressive Web App (PWA)** with Service Workers stays functional without internet. Students save logs to local cache (IndexedDB), and the system automatically syncs to the database when network is restored.

---

## Features

### Core Features

#### 1. Geofencing & Location Validation
- GPS coordinate capture at log entry creation
- Comparison with registered industry location
- Visual status indicators (Within/Outside geofence)
- Haversine distance calculation for accuracy

#### 2. Offline-First Architecture
- **IndexedDB** for local log storage when offline
- **Service Worker** for asset caching
- **Background Sync** for automatic data transfer to server
- **Client-side UUID** generation for deduplication

#### 3. 25-Week Logbook System
- Weekly calendar grid (Monday-Friday)
- Status tracking (Verified, Pending, Flagged)
- Filter tabs (All Weeks, This Week, Pending Review)
- Real-time character counter (500 char limit)

#### 4. Communication Module
- Real-time chat interface
- Call history tracking
- Video consultation interface
- Supervisor-student messaging

#### 5. Supervisor Dashboard
- Student log review interface
- Bulk verification workflows
- Geofencing map view
- Filter by status (All, Pending, Verified, Flagged)

#### 6. Student Dashboard
- Current week overview
- Verified logs count
- Pending reviews count
- Active hours tracking

---

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Routes     │  │  Components  │  │   Layouts    │    │
│  │ (FastHTML)   │  │ (Faststrap)  │  │  (Navbar)    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      Domain Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Services   │  │    Models    │  │  Algorithms  │    │
│  │ (Business)   │  │ (SQLAlchemy) │  │ (Geofence)  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Infrastructure Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Database   │  │   Security   │  │     PWA      │    │
│  │ (PostgreSQL) │  │  (Session)  │  │ (SW/IndexedDB│    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema

```mermaid
erDiagram
    User ||--o{ Log : creates
    User ||--o{ Placement : has
    Placement ||--o{ Log : "recorded in"
    Placement ||--o{ Geofence : has
    Supervisor ||--o{ Student : supervises
    User ||--o{ Message : sends
    
    User {
        uuid id PK
        string email
        string password_hash
        string full_name
        enum role
        boolean is_active
    }
    
    Placement {
        uuid id PK
        uuid student_id FK
        string company_name
        string company_address
        string company_lat
        string company_lng
        float geofence_radius
        date start_date
        date end_date
        enum status
    }
    
    Geofence {
        uuid id PK
        uuid placement_id FK
        string center_lat
        string center_lng
        float radius_meters
        boolean is_active
    }
    
    Log {
        uuid id PK
        uuid student_id FK
        uuid placement_id FK
        date log_date
        string day_of_week
        text activity_description
        string skills_acquired
        enum status
        string latitude
        string longitude
        float distance_from_site
        string supervisor_comment
        datetime created_at
        datetime updated_at
    }
    
    Message {
        uuid id PK
        uuid sender_id FK
        uuid receiver_id FK
        text content
        boolean is_read
        datetime created_at
    }
    
    Call {
        uuid id PK
        uuid caller_id FK
        uuid receiver_id FK
        enum call_type
        int duration_seconds
        datetime started_at
        datetime ended_at
    }
```

---

## Technology Stack

### Backend
- **FastHTML** - Modern Python web framework
- **Faststrap** - Bootstrap components for FastHTML
- **SQLAlchemy** - ORM for database operations
- **PostgreSQL** - Primary database
- **Pydantic** - Data validation
- **Uvicorn** - ASGI server

### Frontend
- **HTMX** - Dynamic HTML updates
- **Bootstrap 5** - UI framework
- **Faststrap** - Pre-built Bootstrap components
- **Bootstrap Icons** - Icon library

### PWA Features
- **Faststrap PWA** - Manifest, generated service worker, and offline shell
- **IndexedDB** - Client-side database
- **Web App Manifest** - Installable app metadata
- **Deferred Sync** - Queued offline logs sync automatically when the app returns online

### Development Tools
- **Python 3.10+**
- **pip** - Package manager
- **Git** - Version control

---

## Screenshots

### Landing Page
![Landing Page](docs/screenshots/student_dashboard.png)
*Modern landing page with dashboard preview*

### Login Screen
![Login](docs/screenshots/login.png)
*Clean authentication interface*

### Student Dashboard
![Student Dashboard](docs/screenshots/student_dashboard.png)
*Personal metrics and quick actions*

### Daily Logbook
![Logbook](docs/screenshots/logbook.png)
*25-week calendar grid with status tracking*

### Supervisor Dashboard
![Supervisor Dashboard](docs/screenshots/supervisor_dashboard.png)
*Student overview and log review*

---

## Installation

### Prerequisites

Before installing, ensure you have the following:

1. **Python 3.10 or higher**
   - Download: [https://www.python.org/downloads/](https://www.python.org/downloads/)
   - During installation, check "Add Python to PATH"

2. **PostgreSQL/Supabase**
   - Local development may use SQLite or PostgreSQL.
   - Production uses Supabase PostgreSQL via `SUPABASE_URL`.

3. **Git** (optional, for cloning)
   - Download: [https://git-scm.com/downloads](https://git-scm.com/downloads)

### Step 1: Download the Project

**Option A: Using Git**
```bash
git clone <repository-url>
cd siwes-logbook-automation
```

**Option B: Download ZIP**
1. Download the project ZIP file
2. Extract to your desired location
3. Open terminal/command prompt in the extracted folder

### Step 2: Set Up Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```env
# Database Configuration
DATABASE_URL_DEV=sqlite:///./siwes_dev.db
SUPABASE_URL=postgresql://postgres.your-project:password@aws-0-region.pooler.supabase.com:6543/postgres

# Security
SECRET_KEY=your-secret-key-here-change-in-production

# LiveKit Calls
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-livekit-api-key
LIVEKIT_API_SECRET=your-livekit-api-secret

# Application
DEBUG=True
ENVIRONMENT=development
AUTO_INIT_DB=False

# Server
HOST=0.0.0.0
PORT=5031
```

### Step 5: Initialize Supabase Database

```bash
python scripts/migrate_to_supabase.py --seed
```

Use `--reset --seed` only when you intentionally want to wipe and recreate the Supabase public schema.

### Step 6: Local Reset/Seed

```bash
python scripts/reset_db.py
python scripts/seed_real_data.py
```

`scripts/reset_db.py` refuses to reset production/Supabase databases unless `ALLOW_DESTRUCTIVE_RESET=YES_I_UNDERSTAND` is set.

### Step 7: Add Real Data Manually

For a simple prompt-based setup, run:

```bash
python scripts/manual_seed.py
```

The wizard asks for supervisors, students, and SIWES center details one by one. Press Enter to accept the default values shown in brackets.

For bulk entry, edit `data/manual_seed_template.json`, then run:

```bash
python scripts/manual_seed.py --json data/manual_seed_template.json
```

The JSON file can contain many supervisors and many students. Existing records are updated by email, so the command is safe to run again after corrections.

### Step 8: Run the Application

```bash
python main.py
```

The application will start on `http://localhost:5031`

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:5031
INFO:     Application startup complete.
```

### Step 9: Access the Application

Open your browser and navigate to:
- **Landing Page**: http://localhost:5031
- **Login**: http://localhost:5031/login
- **Health Check**: http://localhost:5031/health

---

## Deployment Notes

FastAPI Cloud is the recommended hosting target for this FastHTML/Faststrap app.

Before deploying:

```bash
python scripts/migrate_to_supabase.py --seed
```

Production environment variables:

```env
ENVIRONMENT=production
AUTO_INIT_DB=False
SUPABASE_URL=postgresql://...
SECRET_KEY=...
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
```

Use `.env.production.example` as the FastAPI Cloud checklist. Do not import the full local `.env` directly because it contains local-only values such as `DATABASE_URL_DEV`; if `APP_NAME` is used, quote it when it contains spaces.

`AUTO_INIT_DB=False` prevents the web process from mutating Supabase schema during startup. Run schema setup through `scripts/migrate_to_supabase.py` instead.

---

## Usage

### Student Workflow

1. **Login** with student credentials
2. **Dashboard**: View current week stats, verified logs, pending reviews
3. **Logbook**: 
   - Navigate through 25-week calendar
   - Click on a day to add log entry
   - Enter activity description and skills acquired
   - System captures GPS location automatically
4. **Communication**:
   - Chat with supervisor
   - View call history
   - Request video consultation
5. **Profile**: Update personal information and view placement details

### Supervisor Workflow

1. **Login** with supervisor credentials
2. **Dashboard**: View assigned students overview
3. **Logs**: Review student submissions
   - Filter by status (All, Pending, Verified, Flagged)
   - View GPS verification data
   - Add comments and approve/flag entries
4. **Geofencing**: View student location verification
5. **Communication**:
   - Chat with students
   - Initiate video calls

### Offline Mode

When network is unavailable:
1. Student logs are saved to IndexedDB
2. Logs display "Pending Sync" status
3. When connection restores, data syncs automatically
4. Duplicate detection prevents data loss

---

## Project Structure

```
siwes-logbook-automation/
├── app/
│   ├── application/
│   │   └── services/         # Business logic
│   │       ├── auth.py       # Authentication service
│   │       ├── log.py        # Log management
│   │       ├── geofence.py   # Location validation
│   │       ├── sync.py       # Offline sync
│   │       └── notification.py
│   ├── domain/
│   │   └── models/           # SQLAlchemy models
│   │       ├── user.py
│   │       ├── log.py
│   │       ├── placement.py
│   │       ├── call.py
│   │       └── chat.py
│   ├── infrastructure/
│   │   ├── database/         # Database connection
│   │   │   ├── connection.py
│   │   │   └── middleware.py
│   │   ├── repositories/     # Data access layer
│   │   └── security/        # Auth & security
│   │       ├── password.py
│   │       └── session.py
│   └── presentation/
│       ├── assets/          # CSS, JS, PWA files
│       │   ├── custom.css
│       │   ├── anchor-uni.jpeg
│       │   ├── offline_log_sync.js
│       │   ├── offline_resume.js
│       │   └── pwa_install_prompt.js
│       ├── components/      # Reusable UI components
│       │   ├── domain/
│       │   │   ├── landing.py
│       │   │   ├── auth.py
│       │   │   ├── student/
│       │   │   │   ├── dashboard.py
│       │   │   │   ├── logbook.py
│       │   │   │   ├── communication.py
│       │   │   │   └── profile.py
│       │   │   └── supervisor/
│       │   │       ├── dashboard.py
│       │   │       ├── logs.py
│       │   │       ├── geofencing.py
│       │   │       └── communication.py
│       │   ├── shared/
│       │   │   ├── theme.py
│       │   │   └── icons.py
│       │   └── ui/
│       │       ├── layouts.py
│       │       ├── navigation.py
│       │       ├── cards.py
│       │       └── forms.py
│       └── routes/          # Route handlers
│           ├── auth.py
│           ├── student.py
│           ├── supervisor.py
│           ├── chat.py
│           ├── calls.py
│           └── notifications.py
├── scripts/
│   ├── reset_db.py
│   └── seed_real_data.py
├── data/
│   ├── students.json
│   └── supervisors.json
├── docs/
│   └── screenshots/
├── .env
├── .env.example
├── main.py                  # Application entry point
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Contributing

This is an academic project (Final Year Project) for Anchor University.

**Project Owner**: Asuku David

**Developer**: Olorundare Micheal

For questions or issues, contact the development team.

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## Acknowledgments

- **FastHTML** framework by Answer.AI
- **Faststrap** for Bootstrap components
- **Bootstrap** team for the UI framework
- **Anchor University** Computer Science Department

---

**Built with ❤️ using FastHTML and Faststrap**
