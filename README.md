# AI Assistant (FastAPI + Login UI + Supabase Ready)

## Stack
- FastAPI backend (`app/api_server.py`)
- Custom frontend (`frontend/`)
- SQLAlchemy models (`app/db.py`)
- Gemini API for generation
- Optional legal KB retrieval

## Use Supabase (recommended)
1. Create a Supabase project.
2. Open Supabase: `Project Settings -> Database -> Connection string (URI)`.
3. Copy `.env.example` to `.env`.
4. Set:
   - `GOOGLE_API_KEY=...`
   - `DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?sslmode=require`

## Run locally
```bash
pip install -r requirements.txt
uvicorn app.api_server:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

## Notes
- Tables are auto-created on startup via `init_db()`.
- SQLite fallback is still available if `DATABASE_URL` is not set.
