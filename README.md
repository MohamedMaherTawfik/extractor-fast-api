# EMY PRIVATE AI OS

A local-first, private-first, portable, and modular AI operating-system project. The current backend covers Creator/Content collection and analysis, Pattern/Recipe, Rules, multimodal Generation, Product/Sales, Answer Bot/Customer Service, and governed business-lead acquisition over an Alembic-versioned SQLAlchemy/SQLite core.

## Windows Setup

From the project root, run:

~~~bat
scripts\bootstrap_windows.bat
~~~

The script creates the project-local .venv when needed, upgrades its pip installation, installs requirements, and verifies that Python is running inside the virtual environment.

Use the project interpreter directly for all Python and pip operations:

~~~bat
.venv\Scripts\python.exe
.venv\Scripts\python.exe -m pip
~~~

## Start the Local Backend

~~~bat
scripts\start_backend.bat
~~~

The server binds only to the configured loopback host. Its health endpoint is available at http://127.0.0.1:8000/health.

## Tests

~~~bat
.venv\Scripts\python.exe -m pytest
~~~

## Creator Master

Local endpoints include:

~~~text
GET    /creators
GET    /creators/{id}
POST   /creators
PATCH  /creators/{id}
GET    /creators/{id}/accounts
POST   /creators/{id}/accounts
PATCH  /platform-accounts/{id}
POST   /creator-imports
~~~

The import endpoint accepts multipart CSV or XLSX files. Column aliases are configured in configs/app.yaml, imported files use managed data/imports storage, and no platform network request occurs.

To insert the non-sensitive Creator A/B demo records:

~~~bat
.venv\Scripts\python.exe -m scripts.seed_demo_data
~~~

Database upgrades run automatically at backend startup. They can also be checked explicitly:

~~~bat
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
~~~

## Architecture

See docs/ARCHITECTURE.md. Paid lead providers and real platform/messaging connectors remain intentionally unconfigured; publishing, authentication, and the portable production runtime remain unimplemented. The Windows desktop UI and the open-data Lead Acquisition workspace are implemented and natively verified.

## Pattern and Recipe Engine

Normalized analysis can be mapped into versioned Content DNA, mined inside comparable cohorts, compared or clustered deterministically, and converted into editable generation-plan recipes. Performance results are associations rather than causal claims, and recipes preserve source patterns, contents, creators, confidence, evidence, and immutable version history.

See docs/PATTERN_RECIPE_ENGINE.md for configuration, APIs, evidence, provenance, and causality constraints.

## Answer Bot

The local Answer Bot normalizes conversations, grounds price/stock/order answers in Product/Sales, validates every draft, and auto-sends only low-risk responses through no-network adapters. Sensitive or uncertain cases are routed to human review. See docs/ANSWER_BOT.md for channels, safety, queues, follow-ups, knowledge, CRM signals, and sales drafts.

## Desktop UI development status

The React/TypeScript operator control center, thin operator APIs, frontend tests, and Tauri 2 development configuration are present under `frontend/`. The browser development surface is verified. Native Tauri compilation remains blocked on this host until the Microsoft Visual C++ Build Tools and Windows SDK prerequisites are installed; therefore the Desktop UI project task remains open. See `docs/DESKTOP_UI.md`.
