# Wan2GP Multi-User Platform - MVP Phase 2

## 📋 Overview

Wan2GP Platform is a multi-user web application wrapper around the Wan2GP video generation engine. This document describes the **Phase 2 Foundation** - a complete skeleton for the MVP platform, designed for manager testing.

**Current Status:** Phase 2 Implementation (Foundation Foundation)  
**Next Phase:** Phase 3 (Authentication, Queue, Admin Panel)

---

## 🏗️ Architecture Overview

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                   │
│              Port 5173 | TypeScript | Tailwind CSS            │
│                  - Pages, Components, Hooks                  │
│                  - API Client, State Management              │
└─────────────────────────┬──────────────────────────────────┘
                          │ HTTP/REST
                          │ (Axios)
┌─────────────────────────▼──────────────────────────────────┐
│                Backend (FastAPI + Uvicorn)                  │
│              Port 8000 | Python 3.11+ | CORS                │
│        ┌─────────────────────────────────────────────┐      │
│        │  API Routes & Endpoints                     │      │
│        │  - /health (health check)                   │      │
│        │  - /api/v1/* (core endpoints - Phase 3)    │      │
│        └─────────────────────────────────────────────┘      │
│        ┌─────────────────────────────────────────────┐      │
│        │  Services Layer (Business Logic)            │      │
│        │  - User management (Phase 3)                │      │
│        │  - Job queue management (Phase 3)          │      │
│        │  - Wan2GP integration (Phase 3)            │      │
│        └─────────────────────────────────────────────┘      │
│        ┌─────────────────────────────────────────────┐      │
│        │  Database Layer (SQLAlchemy ORM)            │      │
│        │  - Models, Session Management              │      │
│        │  - Alembic Migrations (future)             │      │
│        └─────────────────────────────────────────────┘      │
└─────────────────────────┬──────────────────────────────────┘
                          │ SQL
┌─────────────────────────▼──────────────────────────────────┐
│              Database (PostgreSQL 14+)                       │
│        (SQLite for development if needed)                   │
│        - Tables: users, generation_jobs, videos, etc.      │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│           Wan2GP Engine (In-Process - Separate)              │
│            - Untouched existing engine                       │
│            - Integration layer (Phase 3)                     │
│            - Models, configs, shared/api                     │
└──────────────────────────────────────────────────────────────┘
```

### MVP Technology Stack

#### Backend
- **Framework:** FastAPI (async, high-performance)
- **Server:** Uvicorn
- **Database:** PostgreSQL 14+ (SQLite for dev)
- **ORM:** SQLAlchemy 2.0
- **Validation:** Pydantic v2
- **Authentication:** JWT + bcrypt (Phase 3)
- **Logging:** Standard Python logging
- **Testing:** pytest + pytest-asyncio

#### Frontend
- **Framework:** React 18
- **Build Tool:** Vite
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **HTTP Client:** Axios
- **State Management:** Zustand
- **Data Fetching:** TanStack React Query
- **Routing:** React Router

#### Storage (MVP)
- **Local Filesystem:** `./generated_videos/`
- **Abstract Layer:** StorageBackend interface (prepare for S3/Azure)
- **Future:** S3/Azure Blob Storage (Phase 3+)

#### Job Queue (MVP - Novel Design)
- **Database:** PostgreSQL `GenerationJobs` table IS the queue
- **Polling:** Single background thread (1 second interval)
- **Locking:** Optimistic locking with `worker_id + locked_until`
- **Progress:** Direct DB writes (no message broker)
- **Future:** Redis + Celery (Phase 3+ upgrade path)

---

## 📁 Project Structure

```
Wan2GP/
├── .env.example                    # Environment template
├── .gitignore                      # Git ignore rules
├── README.md                       # This file
│
├── backend/                        # FastAPI Application
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI app instance
│   │   ├── config.py             # Settings from .env
│   │   ├── api/                  # API route modules
│   │   │   ├── health.py         # Health check endpoint
│   │   │   ├── auth.py           # (Phase 3)
│   │   │   ├── jobs.py           # (Phase 3)
│   │   │   └── admin.py          # (Phase 3)
│   │   ├── core/
│   │   │   ├── exceptions.py     # Custom exceptions
│   │   │   └── logging_config.py # Logging setup
│   │   ├── db/
│   │   │   └── database.py       # SQLAlchemy + PostgreSQL
│   │   ├── models/               # SQLAlchemy ORM models (Phase 3)
│   │   ├── schemas/              # Pydantic request/response schemas (Phase 3)
│   │   ├── services/             # Business logic layer (Phase 3)
│   │   └── workers/              # Background job worker (Phase 3)
│   ├── tests/
│   │   ├── conftest.py           # Test fixtures & DB setup
│   │   ├── test_health.py        # Health check tests
│   │   └── test_auth.py          # (Phase 3)
│   ├── requirements.txt           # Python dependencies
│   └── pytest.ini                 # Test configuration
│
├── frontend/                       # React + Vite Application
│   ├── src/
│   │   ├── main.tsx              # Entry point
│   │   ├── App.tsx               # Root component
│   │   ├── globals.css           # Tailwind CSS
│   │   ├── components/
│   │   │   ├── HealthStatus.tsx  # Status indicator
│   │   │   ├── Header.tsx        # (Phase 3)
│   │   │   └── ...
│   │   ├── hooks/
│   │   │   └── useApi.ts         # API query hooks
│   │   ├── services/
│   │   │   └── api.ts            # Axios API client
│   │   ├── pages/                # Page components (Phase 3)
│   │   └── store/                # Zustand state (Phase 3)
│   ├── public/                    # Static assets
│   ├── index.html                # HTML entry point
│   ├── package.json              # Dependencies
│   ├── tsconfig.json             # TypeScript config
│   ├── vite.config.ts            # Vite configuration
│   ├── tailwind.config.js        # Tailwind configuration
│   └── .gitignore                # Frontend git ignore
│
├── storage/                        # Generated videos directory
│   └── (created at runtime)
│
├── docs/                          # Documentation
│   ├── API.md                     # (Phase 3) API specification
│   ├── DATABASE.md                # (Phase 3) Schema & migrations
│   ├── QUEUE.md                   # (Phase 3) Job queue design
│   └── DEPLOYMENT.md              # (Phase 3) Deployment guide
│
├── wgp.py                         # Existing Wan2GP engine (UNTOUCHED)
├── requirements.txt               # Existing engine dependencies
├── shared/                        # Existing engine modules (UNTOUCHED)
├── models/                        # Model handlers (UNTOUCHED)
├── defaults/                      # Model configs (UNTOUCHED)
└── ...                            # Other existing files
```

---

## 📦 Prerequisites

### Required
- **Python 3.11+**
- **Node.js 18+** (with npm or yarn)
- **PostgreSQL 14+** (or SQLite for development)
- **Git**

### Optional
- **Docker** (for PostgreSQL, future)
- **VS Code** with Python & TypeScript extensions

---

## 🚀 Quick Start

### 1. Clone & Setup Repository

```bash
cd f:\Internship\Wan2GP
git clone <repo-url> .  # Or already in the repo
```

### 2. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
# Minimum required:
# - DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wangp
# - JWT_SECRET_KEY=your-secret-key
```

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# or: source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run backend server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Backend will be available at:** `http://localhost:8000`  
**API Docs (Swagger UI):** `http://localhost:8000/docs`

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

**Frontend will be available at:** `http://localhost:5173`

### 5. Verify Health Check

```bash
# Terminal 1: Backend running
# Terminal 2: Frontend running
# Terminal 3: Test health endpoint
curl http://localhost:8000/api/v1/health

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "2024-01-20T10:30:45.123456",
#   "database": "healthy"
# }
```

---

## ✅ Phase 2 Deliverables (Foundation Only)

### ✓ Completed
- [x] Project structure (backend, frontend, storage, docs)
- [x] FastAPI application skeleton
- [x] Configuration management (.env.example)
- [x] Database connection setup (SQLAlchemy + PostgreSQL)
- [x] Health check endpoint (/api/v1/health)
- [x] React + TypeScript + Vite setup
- [x] Tailwind CSS styling
- [x] API client (Axios with TanStack Query)
- [x] Health status component (frontend)
- [x] Testing framework (pytest + React Testing Library)
- [x] Basic tests (health check, startup)
- [x] Docker configuration template (.env)
- [x] .gitignore with all necessary patterns
- [x] README documentation

### 🔄 In Phase 3
- [ ] User authentication (register, login, JWT refresh)
- [ ] User management (CRUD endpoints)
- [ ] Roles & permissions (admin, user)
- [ ] Video generation job endpoints
- [ ] Job queue implementation (database polling)
- [ ] Background worker (process jobs)
- [ ] Wan2GP integration (call engine API)
- [ ] Admin dashboard
- [ ] Job monitoring & status updates
- [ ] Error handling & logging
- [ ] Integration tests
- [ ] Database migrations (Alembic)

### Future Phases (Post-MVP)
- [ ] Redis job queue (upgrade from DB queue)
- [ ] Celery task scheduler
- [ ] S3/Azure Blob Storage integration
- [ ] Kubernetes deployment
- [ ] Multi-GPU load balancing
- [ ] Advanced admin analytics
- [ ] Webhook notifications
- [ ] API rate limiting & throttling

---

## 🧪 Running Tests

### Backend Tests

```bash
cd backend

# Run all tests
pytest

# Run specific test file
pytest tests/test_health.py

# Run with coverage
pytest --cov=app tests/

# Verbose output
pytest -v
```

### Frontend Tests

```bash
cd frontend

# Run type check
npm run type-check

# Run linting
npm run lint

# Build production
npm run build
```

---

## 🔧 Development Commands

### Backend

```bash
# Start development server (with auto-reload)
cd backend
python -m uvicorn app.main:app --reload

# Run tests
pytest

# Format code (black)
black app tests

# Type checking
mypy app

# Lint (flake8)
flake8 app tests
```

### Frontend

```bash
# Start dev server
cd frontend
npm run dev

# Production build
npm run build

# Preview production build
npm run preview

# Type check
npm run type-check

# Lint
npm run lint
```

---

## 📚 API Documentation

### Base URL
- **Development:** `http://localhost:8000/api/v1`
- **Production:** (Phase 3+)

### Endpoints (Phase 2)

#### Health Check
- **Endpoint:** `GET /health`
- **Description:** Check API and database status
- **Response:**
  ```json
  {
    "status": "healthy",
    "timestamp": "2024-01-20T10:30:45.123456",
    "database": "healthy"
  }
  ```

### Endpoints (Phase 3+)
- `/auth/register` - User registration
- `/auth/login` - User login
- `/auth/refresh` - Token refresh
- `/users` - User management
- `/jobs` - Job creation & status
- `/jobs/{id}` - Job details
- `/videos` - Video listing
- `/admin/dashboard` - Admin panel data

See `docs/API.md` (Phase 3) for full specification.

---

## 🔐 Security Notes

### Phase 2 (MVP Foundation)
- ⚠️ **JWT_SECRET_KEY in .env is placeholder** - Use strong random key in production
- ⚠️ **No authentication implemented** - Coming in Phase 3
- ⚠️ **CORS allows localhost only** - Adjust ALLOWED_ORIGINS for production

### Phase 3+
- [ ] Implement JWT authentication
- [ ] Add RBAC (roles & permissions)
- [ ] Password hashing (bcrypt)
- [ ] Rate limiting
- [ ] SQL injection prevention (already done with SQLAlchemy)
- [ ] CORS production hardening

---

## 🐛 Troubleshooting

### Database Connection Error
```
Error: could not connect to server: Connection refused
```
**Solution:** Ensure PostgreSQL is running and DATABASE_URL is correct in .env

### Port Already in Use
```
Address already in use
```
**Solutions:**
```bash
# Find process using port 8000
netstat -ano | findstr :8000  # Windows
# Kill process or use different port
```

### Frontend Cannot Connect to Backend
```
CORS error in browser console
```
**Solution:** Verify ALLOWED_ORIGINS in `backend/app/config.py` includes frontend URL

### Node Modules Issues
```
npm ERR! ...
```
**Solution:** Clear cache and reinstall
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

---

## 📝 Important Notes

### Wan2GP Engine Integration
- ✅ **Wan2GP engine is UNTOUCHED** in Phase 2
- ✅ **All platform files are SEPARATE** from the engine
- ✅ **Integration happens in Phase 3** via isolated service layer
- ✅ **In-process API call** to `shared.api` (no subprocess overhead)

### Database Design
- ✅ **PostgreSQL ready** (ORM configured)
- ✅ **Schema not created yet** (Phase 3: Alembic migrations)
- ✅ **No premature tables** (foundation only)
- 🔄 **Tables designed:** users, generation_jobs, generated_videos, audit_logs

### Job Queue Strategy (Phase 3)
- **MVP:** Database as queue (simple, single deployment)
- **Polling:** Background thread checks `GenerationJobs` every 1 second
- **Locking:** Optimistic locking prevents duplicate processing
- **Future:** Redis + Celery without rewriting business logic

### Development vs Production
- **Dev:** SQLite database (optional), debug logging, hot reload
- **Production:** PostgreSQL, structured logging, secure JWT secret

---

## 📖 Further Reading

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM Guide](https://docs.sqlalchemy.org/)
- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)

---

## 📊 Project Status

| Task | Phase 2 | Phase 3 | Phase 4+ |
|------|---------|---------|----------|
| Project Structure | ✅ | - | - |
| Backend Foundation | ✅ | - | - |
| Frontend Foundation | ✅ | - | - |
| Authentication | - | 🔄 | - |
| Database Schema | - | 🔄 | - |
| Job Queue | - | 🔄 | - |
| Admin Panel | - | 🔄 | - |
| Redis Integration | - | - | 🔄 |
| Kubernetes Deploy | - | - | 🔄 |

---

## 🤝 Contributing

For Phase 2 maintenance:
1. Keep Wan2GP engine untouched
2. Maintain clear separation between platform and engine
3. Follow the architecture defined in this README
4. Test health check before deployment

---

## ⚖️ License

Same as Wan2GP engine (see LICENSE.txt)

---

**Last Updated:** Phase 2 Foundation  
**Next Milestone:** Phase 3 - Authentication & Queue Implementation
