# Inkloom AI — Brand Governance & Content Policy Auditor

Inkloom AI is an AI-powered brand-governance platform. The system inspects submitted content against approved brand guidelines, terminology, and facts, cites evidence for detected issues, suggests corrections, and empowers human reviewers to revise, compare, and approve final copy.

---

## Architecture Overview

* **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, Lucide React
* **Backend:** Python 3.15, FastAPI, Pydantic, Uvicorn, Google GenAI SDK (`google-genai`), Supabase Python Client (`supabase`)
* **AI Evaluation:** Hybrid deterministic rule engine + Google Gemini API contextual brand tone & claim auditor
* **Review Lifecycle:** Human review state machine (`draft`, `in_review`, `changes_requested`, `approved`, `rejected`) with version snapshots and approval invalidation
* **Brand Guidelines Editor:** Configurable brand identity, prohibited terminology, preferred nomenclature, approved facts, and required disclaimers
* **Revision Diff Viewer:** Side-by-side & stacked diffs, statistical change breakdown, and rule finding resolution tracking
* **Database & Auth:** Supabase PostgreSQL, Supabase Auth, Row Level Security (RLS) multi-tenant isolation, versioned content storage, and immutable decision audit trails
* **Dual-Mode Persistence:** Automatically switches between live Supabase PostgreSQL (when credentials are provided) and isolated in-memory Local Demo Mode (when absent or placeholder). Never silently falls back in production.

---

## Directory Structure

```text
pr1/
├── .gitignore                      # Excludes venv, node_modules, .env, build output
├── .env.example                    # Root environment variable template
├── README.md                       # Comprehensive documentation & setup instructions
├── backend/                        # Python FastAPI service
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application, auth dependencies & API routes
│   │   ├── models/                 # Pydantic schemas (rules, workflow)
│   │   └── engine/                 # Policy engine, Gemini evaluator, Supabase repository, workflow service
│   ├── migrations/                 # PostgreSQL & Supabase SQL migrations
│   │   ├── 001_initial_schema.sql  # 11 tables, constraints, foreign keys, and indexes
│   │   ├── 002_row_level_security.sql # Helper functions, RLS policies & reviewer role enforcement
│   │   └── 003_guidelines_voice_and_tone.sql # Brand description & voice and tone persistence
│   ├── tests/                      # Pytest suite (engine, workflow, Gemini AI, Supabase persistence & live tests)
│   ├── .env.example                # Backend environment variable placeholders
│   ├── requirements.txt            # Python dependencies (google-genai, supabase, pydantic, fastapi)
│   └── venv/                       # Local Python virtual environment
└── frontend/                       # React + TypeScript + Vite client
    ├── src/
    │   ├── App.tsx                 # Studio UI, hybrid audit viewer, human decision gate, storage indicator
    │   ├── index.css               # Design system & styling
    │   ├── main.tsx                # Client entrypoint
    │   ├── components/             # BrandGuidelinesEditor, RevisionDiffViewer
    │   ├── types/                  # TypeScript governance, tenancy & review definitions
    │   └── utils/                  # auth.ts, diffHelpers.ts, guidelinesValidation.ts (all unit-tested)
    ├── package.json
    ├── tailwind.config.js
    └── vite.config.ts
```

---

## Database Architecture & Row Level Security (RLS)

### Migrations

Execute the migrations sequentially in your Supabase project SQL Editor or via Supabase CLI (`supabase db push`):

1. **`backend/migrations/001_initial_schema.sql`**
   - Creates the 11 relational tables: `organisations`, `organisation_members`, `brand_guidelines`, `prohibited_terms`, `preferred_wordings`, `approved_facts`, `required_disclaimers`, `submissions`, `submission_content_versions`, `review_findings`, `review_decisions`.
   - Establishes cascading foreign keys and indexes.

2. **`backend/migrations/002_row_level_security.sql`**
   - Enables RLS across all 11 tables.
   - Installs `current_user_org_ids()` and `current_user_has_role(org_id, required_roles)` security definer functions.
   - Restricts read/write access strictly to members of the target organisation.
   - Enforces **Separation of Duties (Four-Eyes Principle)**: creators cannot approve their own submissions (`creator_id != auth.uid()`).
   - Guarantees **Audit Immutability**: `UPDATE` and `DELETE` queries on `review_decisions` and `submission_content_versions` are unconditionally rejected (`USING false`).

3. **`backend/migrations/003_guidelines_voice_and_tone.sql`**
   - Adds `description` and `voice_and_tone` columns to `public.brand_guidelines` to persist editorial guidelines and brand mission data.

---

## Supabase Authentication & Multi-Tenancy

* **JWT Verification:** Incoming requests with `Authorization: Bearer <token>` are cryptographically inspected (`HS256`, signature, expiration, issuer) against `SUPABASE_JWT_SECRET` and verified via Supabase Auth API (`client.auth.get_user`).
* **Untrusted Client Inputs:** Client-supplied user IDs, roles, and org headers are never trusted. Roles are strictly queried from `public.organisation_members` in the database.
* **Separation of Duties:** If a user with the `reviewer` role attempts to approve content they authored (`creator_id == reviewer_id`), both the FastAPI application and PostgreSQL RLS policy reject the transaction.
* **Session Lifecycle:** The frontend restores authenticated sessions from `localStorage`, checks expiration, injects Bearer tokens into API requests, and safely clears expired or invalidated sessions upon receiving a 401 response.

---

## Getting Started on Windows

### 1. Backend Setup & Configuration

Open PowerShell in the repository root:

```powershell
# Navigate to the backend directory
cd backend

# Create virtual environment (if not already created)
python -m venv venv

# Install backend dependencies
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# Configure environment variables
copy .env.example .env
# Edit .env and configure keys:
# GEMINI_API_KEY=AIzaSy...
# GEMINI_MODEL=gemini-2.5-flash
# SUPABASE_URL=https://your-project-ref.supabase.co
# SUPABASE_ANON_KEY=eyJhbGciOi...
# SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOi... (optional: for backend tests/admin)
# SUPABASE_JWT_SECRET=your_jwt_secret_here

# Run FastAPI development server
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

> [!NOTE]
> **Dual-Mode Persistence (Offline & Local Demo Mode):**
> - If `SUPABASE_URL` or `SUPABASE_ANON_KEY` is omitted or left as placeholders, the service runs in **Local Demo Mode (In-Memory)** with pre-seeded NovaSound Audio demo data.
> - If `ENVIRONMENT=production` is set, missing Supabase credentials immediately raise HTTP 503 instead of falling back to in-memory mode.
> - All unit tests run 100% offline without requiring network credentials.

### 2. Frontend Setup

In a second terminal:

```powershell
# Navigate to the frontend directory
cd frontend

# Install dependencies (use npm.cmd if PowerShell script policy blocks npm)
npm.cmd install

# Run the Vite development server
npm.cmd run dev
```

The frontend client will be available at `http://localhost:5173`.

---

## Running Verification & Tests

### Backend Unit & Persistence Tests (77 Passing Tests, 9 Skipped)

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend/tests
```

* **Deterministic Engine:** Prohibited terms, preferred nomenclature, approved facts, required disclaimers.
* **Gemini Evaluator:** Contextual tone, claims, disclaimer compliance (mocked & offline).
* **Human Review State Machine:** Version increments, approval invalidation, mandatory comments.
* **Brand Guidelines Editor & Diff:** Dynamic rule updates, reset to baseline, side-by-side diff computation.
* **Supabase Persistence & Authorization:** In-memory repository queries, separation of duties, role checks, JWT verification.
* **Live Database Tests (9 tests):** Automatically skip cleanly when real credentials are absent; execute against real Supabase when configured:
  1. `test_live_database_connection`
  2. `test_live_cross_tenant_isolation_and_rls`
  3. `test_live_authentication`
  4. `test_live_unauthorized_access`
  5. `test_live_reviewer_permissions`
  6. `test_live_separation_of_duties_at_database_level`
  7. `test_live_version_history_persistence`
  8. `test_live_guidelines_persistence`
  9. `test_live_audit_immutability_at_database_level`

### Frontend Unit Tests (16 Passing Tests)

```powershell
npm.cmd --prefix frontend test
```

Tests cover:
* `src/utils/auth.test.ts`: Session storage, restoration, expiration validation, header creation.
* `src/utils/diffHelpers.test.ts`: Version validation, finding resolution classification, delta calculation.
* `src/utils/guidelinesValidation.test.ts`: Brand profile, prohibited term regex, facts, and disclaimers validation.

### Frontend Linter & Production Build

```powershell
# Run Oxlint
npm.cmd --prefix frontend run lint

# Run TypeScript check & Vite production build
npm.cmd --prefix frontend run build
```
