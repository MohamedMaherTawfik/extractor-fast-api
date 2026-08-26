# EMY Desktop UI and Operator Control Center

## Architecture

EMY Control Center 1.0.0 is implemented in the existing `frontend/` directory with React, TypeScript, Vite, TanStack Query, React Router, and a Tauri 2 development shell. The UI is presentation and interaction only. Product prices, inventory, balances, generation readiness, rule decisions, MSC posting readiness, and message-send policy remain backend responsibilities.

~~~text
Tauri WebView / browser development surface
  -> route-level error boundaries and feature-discovered navigation
  -> typed API client + TanStack Query server cache
  -> FastAPI service/repository boundary
  -> existing domain engines and SQLite
~~~

Only harmless preferences—language, theme, and sidebar state—are stored in browser local storage. Customer, financial, content, and credential data are never stored there.

## Discovery, API, and realtime strategy

Startup calls `GET /system/capabilities`. This returns actual module versions and availability, including the available Lead Engine and unavailable Publishing feature. Navigation hides unavailable domain modules. The thin operator endpoints provide:

- `/system/health-detail` for backend, database, storage, queue, generation, messaging, and MSC status;
- `/system/dashboard` and `/system/notifications` for live operational counts and alerts;
- `/system/search` for parameterized Product/SKU, Customer, Order, Invoice, Conversation, Recipe, Job, and Asset lookup;
- `/system/workspaces/{name}` for server-paginated read models;
- `/system/settings` for a deliberately secret-free configuration view.

The typed client uses a configurable `VITE_API_URL`, timeout, normalized errors, and per-request IDs. TanStack Query owns server state. Volatile operational cards refresh every 15 seconds and notifications every 30 seconds; the backend advertises adaptive polling until a future SSE/WebSocket event endpoint exists. The app does not fabricate ETAs.

## Routes and operational screens

The application shell includes a collapsible sidebar, top command/search bar, system connection state, user/mode indicator, and notification center. `Ctrl+K` opens global search and commands.

Routes cover Home, Content, Intelligence, Patterns/Recipes, Rules, Generation, Assets, Content Calendar, Products, Customers, Sales, Inventory, Suppliers/Purchases, MSC Intake, Conversations, Customer Service, Approvals, Analytics, Audit, Settings, and Data Acquisition. The Lead workspace reads only from the Lead API and provides source status, safe run setup/dry-run planning, durable progress and controls, server-paginated filters, provenance detail, and bounded CSV/XLSX/Parquet export.

The Home dashboard contains backend-derived queue, content, approval, sales, order, MSC, conversation, and handoff metrics. All list workspaces are server-paginated and use shared loading, empty, error, table, status, and detail-drawer components. No production sample rows or invented charts are rendered.

Generation has Jobs, Create, Providers/Models, and QA views. The Create workbench inspects an immutable backend Generation Contract. Its execute action stays disabled unless the contract status returned by the backend is `READY`. Creative spec/constraints are collapsible and never expose provider secrets.

Conversation operations use a desktop three-column layout: conversation queue, message thread/draft approvals, and customer/handoff context. Approval, sending, replies, assignment, and follow-up affordances call backend workflows rather than provider SDKs.

MSC offers staged batch/review workspaces and a Tauri dialog restricted to supported file extensions. Only transient base filenames are shown; absolute paths are not persisted or used as business identifiers. The Content Calendar is explicitly planning/read-only because Publishing is unavailable.

## RTL, themes, and accessibility

Arabic is the default and sets `dir=rtl`; English switches the complete shell to LTR. Mixed IDs and JSON remain readable. Light, dark, and system themes use shared design tokens. The shell supports keyboard navigation, visible focus, labelled controls/dialogs, status text in addition to color, reduced motion, responsive desktop widths, and semantic tables. Major routes are protected by error boundaries, including a usable offline diagnostic state.

## Tauri security

The Tauri 2 configuration disables bundling for this development phase. Its capability grants only `core:default` and the open-file dialog. There is no shell, process, unrestricted filesystem, updater, or arbitrary command permission. A restrictive CSP allows only the local backend connection and Tauri IPC/assets. The React application never receives API keys.

WebView2 151 is present. Rust 1.98.0 and Cargo 1.98.0 use the stable `x86_64-pc-windows-msvc` toolchain. Visual Studio Build Tools 2022 17.14.39 supplies MSVC v143 14.44, CMake 3.31.6, and Windows SDK 10.0.26100.0. Native `tauri dev` and optimized `tauri build` both compile successfully on this host.

Native verification used the real Tauri WebView2 window with the local FastAPI backend. It covered the app shell, backend connection, core operational routes, and Data Acquisition. The Lead audit opened New Run, returned a 514-job nationwide dry-run plan without collection, showed two completed bounded live source runs, rendered 20 real Cairo pharmacy leads, and opened canonical/source/provenance detail. This is a documented native smoke/E2E verification; the repository does not add a separately maintained Windows UI automation harness in this phase.

## Development and testing

Frontend-only development:

~~~powershell
cd frontend
npm run dev
~~~

Backend development:

~~~powershell
.\.venv\Scripts\python.exe -m backend.main
~~~

One-command native development:

~~~powershell
scripts\dev_desktop.ps1
~~~

Use `scripts\dev_desktop.ps1 -WebOnly` for the browser development surface. The launcher starts the project interpreter in a hidden child process, waits for health, runs the selected frontend, and stops only the backend process it created.

Verification:

~~~powershell
cd frontend
npm test
npm run build
npm run tauri -- info
cd ..
.\.venv\Scripts\python.exe -m pytest
~~~

Frontend tests mock only the local backend boundary and cover the shell, feature gate, navigation, command palette, RTL/LTR, status/table components, loading/offline behavior, READY/BLOCKED generation contracts, and the Lead workspace. The separate bounded audit called real Overture and OSM endpoints. Portable Python, installers, embedded databases, model/media bundling, signing, and updates remain Prompt 9 work.
