# HR Leave Management – Telegram Bot

A Telegram-based HR leave management system built with **FastAPI**, **PostgreSQL**, and **Redis**. Employees submit leave requests directly through a Telegram bot, and managers approve or reject them with a single click.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Database Schema](#database-schema)
- [Bot Commands](#bot-commands)
- [Leave Request Flow](#leave-request-flow)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Variables](#environment-variables)
  - [Run with Docker Compose](#run-with-docker-compose)
  - [Run Locally](#run-locally)
- [Database Migrations](#database-migrations)
- [Project Structure](#project-structure)

---

## Features

- **Telegram Bot Interface** – Employees interact entirely through Telegram; no web portal required.
- **Role-Based Access Control** – Three roles: `employee`, `manager`, and `hr_admin`.
- **Interactive Leave Request Wizard** – Step-by-step FSM flow with an inline calendar for date selection.
- **Manager Approval Workflow** – Managers receive a notification with one-tap Approve / Reject buttons.
- **Annual Leave Balance Tracking** – Approved leave automatically deducts business days from the employee's balance.
- **Conflict Detection** – Overlapping requests (non-cancelled/rejected) are blocked automatically.
- **Configurable Leave Types** – Each leave type can independently require approval and/or deduct from balance.
- **Audit Logging** – Every status change is recorded with actor, old status, and new status.
- **Docker-Ready** – Single `docker-compose up` spins up the full stack (app, PostgreSQL, Redis).

---

## Tech Stack

| Layer | Technology |
|---|---|
| API / App Server | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) |
| Bot Framework | [python-telegram-bot v21](https://python-telegram-bot.org/) |
| Database | [PostgreSQL 15](https://www.postgresql.org/) via [SQLAlchemy 2 (async)](https://docs.sqlalchemy.org/) |
| Migrations | [Alembic](https://alembic.sqlalchemy.org/) |
| State Management | [Redis 7](https://redis.io/) |
| Settings | [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| Runtime | Python 3.11 |
| Containerisation | Docker + Docker Compose |

---

## Architecture

```
┌─────────────────────────────────────────┐
│              Telegram API               │
└────────────────┬────────────────────────┘
                 │  Long-polling (dev) / Webhook (prod)
┌────────────────▼────────────────────────┐
│           FastAPI Application           │
│  ┌──────────────────────────────────┐   │
│  │       Telegram Bot (PTB)         │   │
│  │  ┌──────────┐  ┌──────────────┐  │   │
│  │  │ Handlers │  │ State Manager│  │   │
│  │  └────┬─────┘  └──────┬───────┘  │   │
│  └───────┼───────────────┼──────────┘   │
│          │               │              │
│  ┌───────▼───────┐  ┌────▼──────┐       │
│  │   Services    │  │   Redis   │       │
│  │ leave_service │  │  (FSM     │       │
│  │ user_service  │  │   state)  │       │
│  └───────┬───────┘  └───────────┘       │
│          │                              │
│  ┌───────▼───────┐                      │
│  │  SQLAlchemy   │                      │
│  │  (async ORM)  │                      │
│  └───────┬───────┘                      │
└──────────┼──────────────────────────────┘
           │
┌──────────▼──────────┐
│     PostgreSQL      │
└─────────────────────┘
```

The bot runs in **polling mode** by default (suitable for development). For production, switch to **webhook mode** using the `/webhook` FastAPI endpoint.

---

## Database Schema

### `users`
| Column | Type | Description |
|---|---|---|
| `id` | Integer PK | Internal user ID |
| `telegram_id` | BigInteger (unique) | Telegram user ID |
| `full_name` | String | Employee display name |
| `role` | Enum | `employee` / `manager` / `hr_admin` |
| `manager_id` | Integer FK → users | Reports-to manager |
| `annual_leave_balance` | Integer | Remaining days (default 14) |

### `leave_types`
| Column | Type | Description |
|---|---|---|
| `id` | Integer PK | — |
| `name` | String (unique) | e.g. "Annual Leave", "Sick Leave" |
| `requires_approval` | Boolean | Whether manager approval is needed |
| `deducts_from_balance` | Boolean | Whether days are deducted from balance |

### `leave_requests`
| Column | Type | Description |
|---|---|---|
| `id` | Integer PK | — |
| `user_id` | Integer FK → users | Requesting employee |
| `leave_type_id` | Integer FK → leave_types | Type of leave |
| `start_date` | Date | First day of leave |
| `end_date` | Date | Last day of leave |
| `reason` | Text (nullable) | Optional reason |
| `status` | Enum | `pending` / `approved` / `rejected` / `cancelled` |
| `created_at` / `updated_at` | Timestamp | Auto-managed |

### `audit_logs`
| Column | Type | Description |
|---|---|---|
| `id` | Integer PK | — |
| `leave_request_id` | Integer FK | Related request |
| `action_type` | String | `created` / `approved` / `rejected` |
| `actor_user_id` | Integer FK | Who performed the action |
| `old_status` | String (nullable) | Previous status |
| `new_status` | String | New status |
| `timestamp` | Timestamp | When the action occurred |

---

## Bot Commands

### Employee Commands

| Command | Description |
|---|---|
| `/start` | Register greeting and status check |
| `/leave` | Start a new leave request wizard |
| `/cancel` | Cancel the current in-progress request |

### HR Admin Commands

| Command | Description |
|---|---|
| `/add_employee <telegram_id> <full_name>` | Add or update an employee under yourself |
| `/list_employees` | List all employees you manage |
| `/set_manager <employee_tg_id> <manager_tg_id>` | Assign a manager to an employee |
| `/admin_help` | Show admin command reference |

> All admin commands require the `hr_admin` role.

---

## Leave Request Flow

```
Employee sends /leave
        │
        ▼
Select Leave Type (keyboard)
        │
        ▼
Select Start Date (inline calendar)
        │
        ▼
Select End Date (inline calendar)
        │
        ▼
Enter Reason (optional, reply "none" to skip)
        │
        ▼
Confirm Summary (Confirm / Cancel keyboard)
        │
        ├─ Cancel → request aborted
        │
        └─ Confirm → LeaveRequest created (status: pending)
                          │
                          ▼
               Manager notified via Telegram
               [Approve] [Reject] inline buttons
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
          Approved               Rejected
    (balance deducted         (no balance change)
     if applicable)
```

---

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/) (recommended)
- **OR** Python 3.11+, PostgreSQL 15, Redis 7 for a local setup
- A [Telegram Bot Token](https://core.telegram.org/bots#botfather) from @BotFather

### Environment Variables

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | *(required)* | Bot token from @BotFather |
| `POSTGRES_SERVER` | `localhost` | PostgreSQL host |
| `POSTGRES_USER` | `hr_admin` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `hr_password` | PostgreSQL password |
| `POSTGRES_DB` | `hr_bot_db` | Database name |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `LOG_LEVEL` | `INFO` | Python logging level |

### Run with Docker Compose

```bash
# 1. Set your bot token in .env
echo "TELEGRAM_BOT_TOKEN=your_token_here" >> .env

# 2. Start the full stack
docker-compose up --build

# 3. Run database migrations (first time only)
docker-compose exec web alembic upgrade head

# 4. (Optional) Load sample data
docker-compose exec db psql -U hr_admin -d hr_bot_db -f /app/init_test_data.sql
```

The API will be available at `http://localhost:8000`. Health check: `GET /health`.

### Run Locally

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your settings

# 4. Apply database migrations
alembic upgrade head

# 5. Start the application
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Database Migrations

This project uses [Alembic](https://alembic.sqlalchemy.org/) for schema migrations.

```bash
# Apply all pending migrations
alembic upgrade head

# Roll back the last migration
alembic downgrade -1

# Generate a new migration after model changes
alembic revision --autogenerate -m "describe your change"

# Show current revision
alembic current
```

---

## Project Structure

```
hr-leave-management/
├── app/
│   ├── bot/
│   │   ├── handlers/
│   │   │   ├── admin.py          # HR admin commands
│   │   │   ├── approval.py       # Manager approve/reject callbacks
│   │   │   └── leave_request.py  # Employee leave request FSM
│   │   ├── __init__.py
│   │   ├── main.py               # Bot setup and polling
│   │   └── state_manager.py      # Redis-backed FSM state
│   ├── core/
│   │   └── config.py             # Pydantic settings
│   ├── db/
│   │   ├── base.py               # SQLAlchemy declarative base
│   │   └── session.py            # Async session factory
│   ├── models/
│   │   ├── audit.py              # AuditLog model
│   │   ├── leave.py              # LeaveRequest, LeaveType models
│   │   └── user.py               # User model
│   ├── services/
│   │   ├── leave_service.py      # Leave business logic
│   │   └── user_service.py       # User CRUD operations
│   └── main.py                   # FastAPI app entry point
├── alembic/                      # Database migration scripts
├── .env.example                  # Environment variable template
├── docker-compose.yml            # Full stack container setup
├── Dockerfile                    # Application container definition
├── init_test_data.sql            # Sample data for development
└── requirements.txt              # Python dependencies
```
