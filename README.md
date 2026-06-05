# 🖥️ IT Monitor Pro

> Production-ready **IT monitoring & incident management** system with REST API, JWT authentication, real-time system metrics, SLA-based escalation, and dashboard.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-000000.svg?logo=flask)](https://flask.palletsprojects.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://www.sqlalchemy.org/)
[![JWT](https://img.shields.io/badge/Auth-JWT-yellow.svg)](https://jwt.io/)
[![Tests](https://img.shields.io/badge/Tests-25%20passed-success.svg)](#-testing)
[![Coverage](https://img.shields.io/badge/Coverage-93%25-brightgreen.svg)](#-testing)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📋 Overview

**IT Monitor Pro** is a back-end service designed for IT operations teams that need to:

- 🔍 **Monitor** infrastructure in real time (CPU, memory, disk, network)
- 🚨 **Detect** anomalies using configurable thresholds
- 🎫 **Track** incidents with SLA-based escalation rules
- 🔐 **Secure** all operations behind JWT authentication
- 📊 **Expose** everything through a clean RESTful API

Built with industry-standard tools (Flask, SQLAlchemy, psutil, Marshmallow) following best practices: Application Factory pattern, Blueprint-based modularity, global error handlers, OWASP-aware authentication.

---

## 🎯 Key Features

| Feature | Status | Description |
|---------|--------|-------------|
| 🔐 JWT Authentication | ✅ | Access + refresh tokens, bcrypt password hashing |
| 👥 User management | ✅ | Register, login, role-based (admin/support) |
| 📡 System metrics | ✅ | CPU, memory, disk, network via `psutil` |
| 🚦 Threshold-based status | ✅ | Auto-classification: OK / WARNING / CRITICAL |
| 🌐 RESTful API | ✅ | Versioned endpoints under `/api/v1/` |
| 🧪 Unit testing | ✅ | 25 tests, 93% coverage on monitoring module |
| 📮 Postman collection | ✅ | Ready-to-import with auto token management |
| 🗄️ Incidents database | 🚧 | In progress |
| 🚨 Alert engine | 🔜 | Planned (Phase 2) |
| 📊 Web dashboard | 🔜 | Planned (Phase 2) |
| 🛠️ CLI tools | 🔜 | Planned (Phase 2) |
| 🐳 Docker deployment | 🔜 | Planned (Phase 3) |

---

## 🏗️ Architecture

```text
+-------------------------------------------------------------+
|                      IT Monitor Pro                          |
+-------------------------------------------------------------+
|                                                              |
|   +--------------+  +--------------+  +--------------+      |
|   |   Auth API   |  |  Metrics API |  |  Health API  |      |
|   |   /auth/*    |  |  /metrics/*  |  |  /health     |      |
|   +------+-------+  +------+-------+  +------+-------+      |
|          |                 |                 |              |
|   +------v-----------------v-----------------v-------+      |
|   |        Flask Application Factory                 |      |
|   |  (JWT manager - Error handlers - Blueprints)     |      |
|   +------+----------------+----------------+---------+      |
|          |                |                |                |
|   +------v------+  +------v------+  +------v--------+      |
|   |   Models    |  |  Services   |  |   Schemas     |      |
|   | (User, ...) |  |(SystemMonitor)|| (Marshmallow) |      |
|   +------+------+  +------+------+  +---------------+      |
|          |                |                                  |
|   +------v------+  +------v------+                          |
|   | SQLAlchemy  |  |   psutil    |                          |
|   |   (SQLite)  |  |  (OS calls) |                          |
|   +-------------+  +-------------+                          |
|                                                              |
+-------------------------------------------------------------+
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Linux / WSL2 / macOS (Windows native should work but is untested)
- `pip` and `venv`

### 1. Clone and set up

```bash
git clone https://github.com/The-Special-One1/it-monitor-pro.git
cd it-monitor-pro

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your secrets (JWT_SECRET_KEY, etc.)
```

### 3. Run the server

```bash
flask --app app.py run --debug
```

Server starts at `http://127.0.0.1:5000`.

### 4. Verify it's working

```bash
curl http://127.0.0.1:5000/
```

You should get a JSON response with available endpoints.

---

## 🔐 Authentication Flow

### Register a new user (admin example)

```bash
curl -X POST http://127.0.0.1:5000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@itmonitor.com",
    "password": "StrongPass1",
    "full_name": "Admin User",
    "role": "admin"
  }'
```

### Login and obtain JWT tokens

```bash
curl -X POST http://127.0.0.1:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@itmonitor.com","password":"StrongPass1"}'
```

Response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "user": { "id": 1, "email": "admin@itmonitor.com", "role": "admin" }
}
```

### Call a protected endpoint

```bash
TOKEN="eyJhbGciOiJIUzI1NiIs..."

curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:5000/api/v1/metrics/system
```

---



## 📡 API Endpoints

### Public

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | API discovery |
| `GET` | `/api/v1/health` | Service liveness check |
| `POST` | `/api/v1/auth/register` | Create a new user |
| `POST` | `/api/v1/auth/login` | Obtain access + refresh tokens |

### Protected (require `Authorization: Bearer <token>`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/auth/me` | Get current user profile |
| `POST` | `/api/v1/auth/refresh` | Get a new access token |
| `GET` | `/api/v1/metrics/health` | Aggregated subsystems status |
| `GET` | `/api/v1/metrics/system` | Full snapshot (CPU + RAM + disk + net) |
| `GET` | `/api/v1/metrics/cpu` | CPU usage + frequency + cores |
| `GET` | `/api/v1/metrics/memory` | RAM + swap usage |
| `GET` | `/api/v1/metrics/disk` | Per-partition disk usage |
| `GET` | `/api/v1/metrics/network` | Network I/O counters |

---

## 📮 Postman Collection

A ready-to-use Postman Collection is included.

1. Import both files from the [`postman/`](postman/) folder:
   - `IT-Monitor-Pro.postman_collection.json`
   - `IT-Monitor-Pro.postman_environment.json`
2. Select the **`IT Monitor Pro - Local`** environment.
3. Run **`Authentication / Login (auto-save token)`** — the access token is saved automatically.
4. All other requests work immediately.

---

## 🧪 Testing

The project uses **pytest** with **pytest-cov** for coverage reporting.

### Run all tests

```bash
pytest -v
```

### Run with coverage

```bash
pytest --cov=app --cov-report=term-missing
```

### Current test stats

```text
collected 25 items
tests/test_system_monitor.py ........................   [100%]
======================== 25 passed in 4.22s ========================

Name                             Stmts   Miss  Cover
-----------------------------------------------------
app/services/system_monitor.py      55      4    93%
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| Web framework | Flask 3.0 (Application Factory + Blueprints) |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (dev) · PostgreSQL (planned for prod) |
| Authentication | Flask-JWT-Extended + bcrypt |
| Validation | Marshmallow |
| System metrics | psutil |
| Testing | pytest · pytest-cov · pytest-flask |
| CLI | Click · Rich |
| Logging | structlog |
| Containers | Docker · docker-compose (planned) |
| API Testing | Postman Collection (included) |

---

## 📂 Project Structure

```text
it-monitor-pro/
├── app/
│   ├── __init__.py           # Application Factory
│   ├── config.py             # Dev / Test / Prod configs
│   ├── extensions.py         # SQLAlchemy, JWT, CORS init
│   ├── api/                  # Blueprints (REST endpoints)
│   │   ├── health.py
│   │   ├── auth.py
│   │   ├── metrics.py
│   │   └── schemas.py
│   ├── models/               # SQLAlchemy ORM models
│   │   └── user.py
│   ├── services/             # Business logic
│   │   └── system_monitor.py
│   └── utils/                # Helpers (security, etc.)
│       └── security.py
├── tests/                    # pytest test suite
│   ├── conftest.py
│   └── test_system_monitor.py
├── postman/                  # Postman collection + env
├── docker/                   # Dockerfile + compose (planned)
├── docs/screenshots/         # Documentation assets
├── cli/                      # CLI tools (planned)
├── app.py                    # Entrypoint
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🗺️ Roadmap

### Phase 1 — Foundation (in progress)
- [x] Flask scaffold + Application Factory
- [x] JWT authentication + user management
- [x] System monitoring service (CPU/RAM/disk/network)
- [x] Unit tests with 93% coverage
- [x] Postman collection
- [ ] Incidents database

### Phase 2 — Core
- [ ] Alert rule engine + SLA-based escalation
- [ ] Incidents management REST API
- [ ] Web dashboard (Flask templates + Chart.js)
- [ ] Technician CLI tool

### Phase 3 — Polish
- [ ] Structured logging
- [ ] Docker + docker-compose
- [ ] CI/CD pipeline (GitHub Actions)

---

## 🔒 Security Notes

- Passwords are hashed with **bcrypt** (cost factor 12)
- JWT tokens use HS256 with a secret loaded from environment variables
- Login responses return a **generic** `"Invalid email or password"` to prevent **user enumeration** attacks (OWASP)
- All sensitive endpoints require `Authorization: Bearer <token>`
- `.env` file is git-ignored — secrets never leave the machine

---

## 👤 Author

**Santo António Arcanjo**

- 🌍 Maputo, Mozambique
- 💼 LinkedIn: www.linkedin.com/in/santo-antónio-b8053b348
- 🐙 [GitHub](https://github.com/The-Special-One1)

Built as a portfolio project demonstrating production-grade backend skills for IT Support / Backend Developer roles.

---

## 📄 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.