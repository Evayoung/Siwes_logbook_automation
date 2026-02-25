# 🎓 SIWES Logbook Automation System

> **An Offline-First, Location-Verified Digital Logbook Platform for Industrial Training**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastHTML](https://img.shields.io/badge/FastHTML-0.6.0+-green.svg)](https://fastht.ml/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-blue.svg)](https://www.postgresql.org/)

---

## 📖 Overview

The **SIWES Logbook Automation System** addresses three critical problems in the current Student Industrial Work Experience Scheme (SIWES) management:

### 1. **The Verification Gap** (Geographical Accountability)
**Problem**: Supervisors cannot verify if students are actually at their workplace, leading to "ghosting" or "back-filling" of logs from home.

**Solution**: **Geofencing** captures GPS coordinates at the moment of entry, ensuring data is only valid if the student is physically within the company's designated radius.

### 2. **Administrative Latency** (Communication Bottlenecks)
**Problem**: Traditional paper logbooks create a "black hole" where supervisors have zero visibility into student progress for months.

**Solution**: **Real-time Chat and Video Consultation** eliminate wait time between student queries and supervisor responses, allowing immediate intervention.

### 3. **Network Instability and Data Loss** (The "Offline" Problem)
**Problem**: Standard web applications fail in remote industrial sites with poor network coverage, forcing students to revert to paper.

**Solution**: **Progressive Web App (PWA)** with Service Workers stays functional without internet. Students save logs to local cache (IndexedDB), and the system automatically syncs to the database when network is restored.

---

## 🎯 Project Objectives

### Aim
Design and implement a secure, offline-capable SIWES management portal that uses **location-based validation** and **video-enabled supervision** to improve the integrity of industrial training.

### Specific Objectives
1. ✅ Review existing SIWES systems to identify technical gaps
2. ✅ Design and implement a web portal for university students and supervisors
3. 🚧 Test and evaluate performance, usability, and reliability

---

## 👥 Target Users

### University Students (Trainees)
- Document daily technical activities for 25 weeks
- Perform location-validated check-ins
- Participate in video consultations with university supervisors

### Institutional (University) Supervisors
- Remotely monitor student progress
- Verify log integrity via geofencing data
- Conduct virtual site visits through integrated communication

---

## 🚀 Core Functionalities

### ✅ Implemented

#### 1. **Geofencing & Location Validation**
- GPS coordinate capture at log entry creation
- Comparison with registered industry location
- Visual status indicators (Within/Outside geofence)
- Haversine distance calculation for accuracy

#### 2. **Offline-First Architecture**
- **IndexedDB** for local log storage when offline
- **Service Worker** for asset caching
- **Background Sync** for automatic data transfer to server
- **Client-side UUID** generation for deduplication

#### 3. **25-Week Logbook System**
- Weekly calendar grid (Monday-Friday)
- Status tracking (Verified, Pending, Flagged)
- Filter tabs (All Weeks, This Week, Pending Review)
- Real-time character counter (500 char limit)

#### 4. **Communication Module**
- Real-time chat interface (UI ready)
- Call history tracking
- Video consultation interface (UI ready)
- Supervisor-student messaging

#### 5. **Supervisor Dashboard**
- Student log review interface
- Bulk verification workflows
- Geofencing map view (UI ready)
- Filter by status (All, Pending, Verified, Flagged)

### 🚧 In Progress

#### 1. **WebRTC Video Integration**
- Peer-to-peer video calling
- Socket.io signaling server
- Network quality adaptation

#### 2. **Real-time Communication**
- WebSocket integration for live chat
- Push notifications for messages
- Online/offline status indicators

#### 3. **Geofencing Map**
- Interactive map with Leaflet.js
- Visual radius drawing
- Multi-location support per student

---

## 💻 Technology Stack

### Backend
- **FastHTML** - Python web framework with HTMX
- **SQLAlchemy 2.0** - ORM with PostgreSQL
- **PostgreSQL 14+** - Relational database
- **Pydantic** - Data validation
- **Uvicorn** - ASGI server

### Frontend
- **HTMX** - Dynamic interactions without heavy JavaScript
- **Faststrap** - Bootstrap 5 components for FastHTML
- **Vanilla JavaScript** - PWA features (Service Worker, IndexedDB)
- **Bootstrap 5** - Responsive UI framework

### PWA Features
- **Service Worker** - Offline asset caching
- **IndexedDB** - Client-side database
- **Web App Manifest** - Installable app metadata
- **Background Sync API** - Automatic synchronization

---

## 📦 Setup Guide

### Prerequisites

1. **Python 3.10+** - [Download](https://www.python.org/downloads/)
   - ⚠️ Check "Add Python to PATH" during installation

2. **PostgreSQL 14+** - [Download](https://www.postgresql.org/download/)
   - Remember the `postgres` user password

3. **VS Code** (Recommended) - [Download](https://code.visualstudio.com/)

### Installation Steps

#### 1. Database Setup

Open **pgAdmin 4** or terminal:

```bash
psql -U postgres
CREATE DATABASE siwes_db;
\q
```

#### 2. Clone Repository

```bash
git clone <repository-url>
cd siwes-logbook-automation
```

#### 3. Create Virtual Environment

**Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

#### 4. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 5. Environment Configuration

Create `.env` file:

```ini
# Database
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/siwes_db

# Security
SECRET_KEY=your-super-secret-key-change-this

# Application
DEBUG=True
ENVIRONMENT=development
CALL_RING_TIMEOUT_SECONDS=75

# Server
HOST=0.0.0.0
PORT=5001
```

#### 6. Initialize Database

```bash
python reset_db.py
```

**Test Credentials:**
- Student: `student@example.com` / `password`
- Supervisor: `supervisor@example.com` / `password`

#### 7. Run Application

```bash
python main.py
```

Visit: http://localhost:5001

---

## 📁 Project Structure

```
siwes-logbook-automation/
├── app/
│   ├── application/          # Business logic
│   │   └── services/         # Auth, Log, Sync, Geofence services
│   ├── domain/               # Domain models
│   │   └── models/           # User, Log, Placement, Geofence
│   ├── infrastructure/       # Infrastructure layer
│   │   ├── database/         # Connection, middleware
│   │   ├── repositories/     # Data access layer
│   │   └── security/         # Password, session management
│   ├── presentation/         # Presentation layer
│   │   ├── assets/           # CSS, PWA/service-worker, notification scripts
│   │   ├── components/       # UI components
│   │   │   ├── domain/       # Student & Supervisor components
│   │   │   └── ui/           # Layouts, navigation
│   │   └── routes/           # Route handlers
│   └── config.py             # Application configuration
├── main.py                   # Application entry point
├── seed_db.py                # Database seeding
├── reset_db.py               # Database reset
├── requirements.txt          # Dependencies
└── README.md                 # This file
```

---

## ✅ What's Implemented

### Core Infrastructure
- [x] Clean Architecture (Domain, Application, Infrastructure, Presentation)
- [x] SQLAlchemy ORM with PostgreSQL
- [x] Session-based authentication with RBAC
- [x] Database middleware for automatic session management
- [x] Password hashing with bcrypt

### Student Portal
- [x] Dashboard with metrics (current week, verified logs, pending, hours)
- [x] 25-week logbook calendar (Mon-Fri grid)
- [x] GPS-verified log entry form
- [x] Offline support (IndexedDB + Service Worker)
- [x] Filter tabs with active states (All, This Week, Pending)
- [x] Communication module (Chat + Call History)
- [x] Profile page

### Supervisor Portal
- [x] Dashboard overview
- [x] Log review with bulk actions
- [x] Filter tabs (All, Pending, Verified, Flagged)
- [x] Detailed log inspection with GPS data
- [x] Geofencing map interface (UI ready)
- [x] Communication with students

### Backend Services
- [x] AuthService (registration, login, password management)
- [x] LogService (CRUD, GPS validation, geofencing)
- [x] SyncService (offline sync, deduplication)
- [x] GeofenceService (Haversine distance calculation)

### PWA Features
- [x] Service Worker for offline caching
- [x] IndexedDB for local storage
- [x] Background sync queue
- [x] Web App Manifest

---

## 🚧 In Progress

### Current Sprint
- [ ] **WebRTC Video Integration**
  - Socket.io signaling server
  - Peer-to-peer connection setup
  - Camera/microphone permissions

- [ ] **Real-time Chat**
  - WebSocket server
  - Message persistence
  - Push notifications

- [ ] **Interactive Geofencing Map**
  - Leaflet.js integration
  - Radius drawing tools
  - Save coordinates to database

---

## 🗺️ Roadmap

### Phase 1: Core Features (75% Complete)
- [x] Offline-first PWA with IndexedDB
- [x] GPS-verified logging with geofencing
- [x] 25-week logbook interface
- [x] Student and supervisor dashboards (UI)
- [x] Communication module (UI)
- [ ] WebRTC video calls (peer-to-peer)
- [ ] Real-time chat with WebSocket

### Phase 2: Data Integration & Completion (Remaining 25%)
- [ ] **Connect Supervisor Logs to Real Data**
  - Currently using mock data, need to fetch from database
  - Implement actual approval/flagging workflow
  - Save supervisor comments to database

- [ ] **Interactive Geofencing Map**
  - Integrate Leaflet.js for map display
  - Visual radius drawing and editing
  - Save geofence coordinates to database

- [ ] **WebRTC Video Consultation**
  - Socket.io signaling server setup
  - Peer-to-peer video connection
  - Call initiation and termination

- [ ] **Real-time Chat**
  - WebSocket server integration
  - Message persistence to database
  - Online/offline status indicators

---

## 📊 Evaluation Metrics

### Location Accuracy
- Geofencing algorithm success rate in identifying unauthorized logging
- GPS coordinate precision within ±10 meters

### Synchronization Reliability
- Speed of data transfer from offline to cloud
- Success rate of background sync operations
- Data integrity after sync

### User Satisfaction
- Ease of use ratings from pilot group
- Perceived reduction in administrative effort
- Mobile responsiveness feedback

---

## 🚫 Out of Scope

The following are explicitly excluded from this project:

- ❌ ITF allowance payments or financial transactions
- ❌ Native Android (.apk) or iOS app store deployment
- ❌ AI-based student-company matching algorithms
- ❌ Deployment to production servers (handled separately)

---

## 📸 Screenshots

### Login Screen
![Login](docs/screenshots/login.png)

### Student Dashboard
![Student Dashboard](docs/screenshots/student_dashboard.png)

### Daily Logbook
![Logbook](docs/screenshots/logbook.png)

### Supervisor Dashboard
![Supervisor Dashboard](docs/screenshots/supervisor_dashboard.png)

---

## 🤝 Contributing

This is an academic project. For questions or issues, contact the development team.
meshelleva@gmail.com

---

## 📄 License

MIT License - See LICENSE file for details.

---

**Built with ❤️ using FastHTML and Python**
