# RepoMind AI

AI-powered GitHub repository analyzer (MVP): enter a **public GitHub repository URL**, inspect its structure, generate a grounded overview, and ask questions about indexed source files.

## Stack
- Frontend: React + Vite
- Backend: FastAPI + httpx
- Optional LLM: Groq-compatible chat completions API (configured through environment variables)
- MVP retrieval: lightweight keyword ranking (no vector database required yet)

## Requirements
- Python 3.11+
- Node.js 20+
- Optional: Groq API key for LLM-generated summaries and answers

## Run locally

### 1. Backend
```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```
Backend: http://127.0.0.1:8000  
API docs: http://127.0.0.1:8000/docs

### 2. Frontend
In a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Frontend: http://localhost:5173

## Optional LLM configuration
Edit `backend/.env`:
```env
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=your_key_here
LLM_MODEL=your-current-supported-model
```
Choose a model currently available to your provider account. If the key is missing, the app uses a deterministic repository overview and retrieval-based answer fallback.

## MVP limitations
- Public repositories only.
- Files are capped by count and size to avoid runaway requests.
- This app does not execute repository code.
- LLM output is best-effort; validate findings against the cited source.
- Keyword retrieval is intentionally simple. Upgrade to embeddings + Chroma after the MVP works.
- Never commit `.env` or API keys.

## Suggested next milestones
1. Add a background job queue and persistent analysis storage.
2. Add language-specific parsers and dependency graphs.
3. Add embeddings + Chroma for semantic retrieval.
4. Add automated tests, cache by commit SHA, and deploy.
