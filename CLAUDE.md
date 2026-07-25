# AI PDF Chat

Chat with uploaded PDFs using retrieval-augmented generation (RAG).

## Stack

- **Backend:** FastAPI, pypdf, sentence-transformers, OpenAI-compatible LLM
- **Frontend:** Vite + React + TypeScript
- **Storage:** Local filesystem + in-memory / JSON vector index for demos

## Layout

```
backend/
  api/         # HTTP routes (auth, documents, chat)
  services/    # PDF parse, embeddings, RAG chat engine
  models/      # Pydantic schemas + domain models
frontend/src/  # React UI
tests/         # Pytest suite
```

## Quick start

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # set OPENAI_API_KEY (or compatible)

uvicorn backend.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/auth/register` | Create user |
| POST | `/api/auth/login` | Get JWT |
| POST | `/api/documents/upload` | Upload PDF |
| GET | `/api/documents` | List documents |
| DELETE | `/api/documents/{id}` | Remove document |
| POST | `/api/chat` | Ask a question over docs |
| GET | `/api/chat/{session_id}` | Fetch session history |

## Agent rules

1. Keep RAG pipeline in `backend/services/` — do not put chunking/LLM logic in routers.
2. Prefer typed Pydantic models in `backend/models/`.
3. Frontend talks only to `/api/*`; never call OpenAI from the browser.
4. Add or update tests under `tests/` for new endpoints and services.
5. Do not commit `.env`, uploaded PDFs, or vector store dumps.

## Test

```bash
pytest tests/ -q
```
