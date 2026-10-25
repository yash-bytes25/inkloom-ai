# Inkloom AI — Brand Governance & Content Policy Auditor

Inkloom AI is an AI-powered brand-governance platform. The system inspects submitted content against approved brand guidelines, terminology, and facts, cites evidence for detected issues, suggests corrections, and empowers human reviewers to revise and approve final copy.

---

## Architecture Overview

* **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, Lucide React
* **Backend:** Python 3.15, FastAPI, Pydantic, Uvicorn
* **Database & Auth (Next Phase):** Supabase PostgreSQL, Supabase Auth, Row Level Security, Supabase Storage
* **AI Evaluation (Next Phase):** Hybrid deterministic rule validation + Google Gemini API contextual auditor

---

## Directory Structure

```text
pr1/
├── .gitignore                      # Excludes venv, node_modules, .env, build output
├── README.md                       # Documentation & setup instructions
├── backend/                        # Python FastAPI service
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py                 # FastAPI application with /api/health
│   ├── .env.example                # Safe environment variable placeholders
│   ├── requirements.txt            # Python dependencies
│   └── venv/                       # Local Python virtual environment
└── frontend/                       # React + TypeScript + Vite client
    ├── src/
    │   ├── App.tsx                 # Foundation UI & API health status check
    │   ├── index.css               # Design system & Tailwind styling
    │   └── main.tsx                # Client entrypoint
    ├── package.json
    ├── tailwind.config.js
    └── vite.config.ts
```

---

## Getting Started on Windows

### 1. Backend Setup

Open PowerShell or Command Prompt in the repository root:

```powershell
# Navigate to the backend directory
cd backend

# Create virtual environment (if not already created)
python -m venv venv

# Install backend dependencies
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# Copy environment template
copy .env.example .env

# Run FastAPI development server
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

The backend health endpoint will be live at:
* **Health Check:** `http://127.0.0.1:8000/api/health`
* **Interactive OpenAPI Docs:** `http://127.0.0.1:8000/docs`

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

The frontend client will be available at:
* `http://localhost:5173`

> [!NOTE]
> **Windows PowerShell Execution Policy Note:**
> If PowerShell blocks `npm` or script activation, use `npm.cmd` and `npx.cmd`, or run:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
> ```
