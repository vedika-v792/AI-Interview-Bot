# AI Interview Coach 🎙️

An AI-powered mock interview tool built with **FastAPI** + **Groq (Llama 3.3)**. Practice role-specific interview questions, get instant constructive feedback after each answer, and receive a final score with improvement areas after 5 questions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          Browser                                │
│  (Vanilla JS — holds conversation history in a JS array,        │
│   sends full history with every API request)                    │
└────────────────────────┬────────────────────────────────────────┘
                         │  HTTPS  (JSON over REST)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              FastAPI Backend  (Railway / Docker)                 │
│                                                                 │
│  GET  /          → serves index.html                            │
│  POST /api/start → generates opening interview question         │
│  POST /api/answer→ grades answer, returns next question OR      │
│                    final summary + score                        │
│                                                                 │
│  ⚠️  GROQ_API_KEY is stored here ONLY — never sent to           │
│      the browser.                                               │
└────────────────────────┬────────────────────────────────────────┘
                         │  HTTPS  (Groq API)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Groq API                                  │
│              model: llama-3.3-70b-versatile                     │
└─────────────────────────────────────────────────────────────────┘
```

**Stateless design:** The frontend (browser) is the source of truth for conversation history.  
Each `/api/answer` request carries the full `history` array so the backend remains stateless — no session storage or database needed in this version.

---

## Features

- 🎯 **4 interview roles** — Software Engineer, Data Analyst, Product Manager, General
- 💬 **Chat-style UI** — bot bubbles left, user bubbles right, animated typing indicator
- 📊 **Progress bar** — "Question 3 of 5" tracked live
- ✅ **Instant feedback** — 2-3 sentence constructive feedback after every answer
- 🏆 **Final summary** — overall score out of 10, holistic performance summary, 3 improvement areas, and a full Q&A review accordion
- 📱 **Mobile responsive** via Tailwind CSS (CDN)

---

## Local Development

### Prerequisites

- Python 3.10+
- A [Groq API key](https://console.groq.com) (free, no billing required)

### 1 — Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/my-interview-bot.git
cd my-interview-bot

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2 — Configure environment

```bash
cp .env.example .env
# Open .env and fill in your Groq API key:
#   GROQ_API_KEY=gsk_...
```

### 3 — Run

```bash
uvicorn main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.  
Interactive API docs are available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Deployment on Railway

### Step-by-step

1. **Push to GitHub**
   ```bash
   git init && git add . && git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/my-interview-bot.git
   git push -u origin main
   ```

2. **Create a Railway project**
   - Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**
   - Connect your GitHub account and select your repo

3. **Railway auto-detects the `Procfile`** and uses it as the start command:
   ```
   web: uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
   No manual build or start command configuration needed.

4. **Environment variables** — add these in the Railway dashboard under *Variables*:

   | Key | Value |
   |-----|-------|
   | `GROQ_API_KEY` | `gsk_...` |
   | `ALLOWED_ORIGINS` | `https://your-app-name.up.railway.app` |

5. **Deploy** — Railway deploys automatically on every push to `main`.

> **Tip:** Railway's free tier (Hobby plan) keeps your app running without cold starts — unlike Render's free tier which spins down after inactivity.

---

## Docker

Build and run locally with Docker:

```bash
docker build -t interview-coach .
docker run -p 8000:8000 \
  -e GROQ_API_KEY=gsk_... \
  -e ALLOWED_ORIGINS=http://localhost:8000 \
  interview-coach
```

> **AWS App Runner alternative:** The same `Dockerfile` can be deployed directly via [AWS App Runner](https://aws.amazon.com/apprunner/). Push the image to ECR, create an App Runner service pointing to it, and inject `GROQ_API_KEY` + `ALLOWED_ORIGINS` as App Runner environment variables. App Runner auto-scales and handles TLS termination out of the box — a strong production alternative to Railway.

---

## Project Structure

```
my-interview-bot/
├── main.py              # FastAPI app — routes, Pydantic models, LLM calls
├── templates/
│   └── index.html       # Single-page frontend (Tailwind CDN + vanilla JS)
├── static/              # Optional: extra JS/CSS assets
├── requirements.txt
├── Procfile             # Railway start command: uvicorn main:app --host 0.0.0.0 --port $PORT
├── .env.example         # Template — copy to .env and fill in secrets
├── .gitignore           # Excludes .env, __pycache__, venvs, etc.
├── Dockerfile           # Python 3.12-slim, uvicorn on port 8000
└── README.md
```

---

## API Reference

The full OpenAPI spec is auto-generated at `/docs` (Swagger UI) and `/redoc`.

### `POST /api/start`

Start a new interview session.

**Request**
```json
{ "role": "Software Engineer" }
```

**Response**
```json
{ "question": "Walk me through how you'd design a URL shortener at scale.", "question_number": 1 }
```

---

### `POST /api/answer`

Submit the candidate's answer to the current question.

**Request**
```json
{
  "role": "Software Engineer",
  "question": "Walk me through how you'd design a URL shortener at scale.",
  "answer": "I'd use a hash function to generate short codes...",
  "question_number": 1,
  "history": []
}
```

**Response (intermediate question)**
```json
{
  "feedback": "Good high-level thinking. Consider discussing collision handling and cache invalidation.",
  "next_question": "How do you approach debugging a performance issue in production?",
  "question_number": 2,
  "is_final": false,
  "final_summary": null,
  "score": null
}
```

**Response (final question, `question_number == 5`)**
```json
{
  "feedback": "Strong closing answer demonstrating ownership.",
  "next_question": null,
  "question_number": 5,
  "is_final": true,
  "final_summary": "You demonstrated solid technical knowledge...\n\n**Key improvement areas:**\n• ...",
  "score": 7
}
```

---

## Future Work

### 1 — Persistent Session Storage (Supabase / Postgres)

In this version the backend is stateless and history lives only in the browser. A natural next step is to persist each session to a database for history, analytics, and export features.

**Proposed schema:**

```sql
CREATE TABLE interview_sessions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  role            TEXT        NOT NULL,
  question_number INT         NOT NULL,
  question        TEXT        NOT NULL,
  answer          TEXT        NOT NULL,
  feedback        TEXT        NOT NULL,
  score           INT,                      -- NULL until final question
  created_at      TIMESTAMPTZ DEFAULT now()
);
```

Integration options:
- **Supabase** — drop-in Postgres with a REST/realtime layer; add `supabase-py` to `requirements.txt` and call `supabase.table("interview_sessions").insert(...)` after each `/api/answer`.
- **Raw Postgres** — use `asyncpg` or `SQLAlchemy 2.x` with async support.

### 2 — Rate Limiting

For production, add per-IP rate limiting to prevent API key exhaustion:

```python
# Example using slowapi (a FastAPI-compatible limiter)
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/answer")
@limiter.limit("10/minute")
async def submit_answer(request: Request, body: AnswerRequest): ...
```

Consider also adding a daily cap per user once authentication is added.

### 3 — Other Ideas

| Feature | Notes |
|---------|-------|
| User authentication | Clerk or Supabase Auth; link sessions to accounts |
| Audio answers | Web Speech API in browser → transcribe → send as text |
| Difficulty levels | Easy / Medium / Hard prompts per role |
| Share report | Generate a PDF summary of the interview session |
| Leaderboard | Aggregate anonymised scores by role for benchmarking |
