# AI Interview Coach 🎙️

An AI-powered mock interview tool built with **FastAPI** + **Anthropic Claude**. Practice role-specific interview questions, get instant constructive feedback after each answer, and receive a final score with improvement areas after 5 questions.

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
│              FastAPI Backend  (Render / Docker)                 │
│                                                                 │
│  GET  /          → serves index.html                            │
│  POST /api/start → generates opening interview question         │
│  POST /api/answer→ grades answer, returns next question OR      │
│                    final summary + score                        │
│                                                                 │
│  ⚠️  ANTHROPIC_API_KEY is stored here ONLY — never sent to      │
│      the browser.                                               │
└────────────────────────┬────────────────────────────────────────┘
                         │  HTTPS  (Anthropic Messages API)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Anthropic API                                │
│              model: claude-3-5-sonnet-20241022                  │
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
- An [Anthropic API key](https://console.anthropic.com/)

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
# Open .env and fill in your Anthropic API key:
#   ANTHROPIC_API_KEY=sk-ant-...
```

### 3 — Run

```bash
uvicorn main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.  
Interactive API docs are available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Deployment on Render

### Step-by-step

1. **Push to GitHub**
   ```bash
   git init && git add . && git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/my-interview-bot.git
   git push -u origin main
   ```

2. **Create a Render Web Service**
   - Go to [render.com](https://render.com) → **New → Web Service**
   - Connect your GitHub repo
   - Set **Runtime** to `Python 3`

3. **Build & Start commands**
   | Setting | Value |
   |---------|-------|
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `uvicorn main:app --host 0.0.0.0 --port 8000` |

4. **Environment variables** — add these in the Render dashboard under *Environment*:

   | Key | Value |
   |-----|-------|
   | `ANTHROPIC_API_KEY` | `sk-ant-...` |
   | `ALLOWED_ORIGINS` | `https://your-app-name.onrender.com` |

5. **Deploy** — click *Create Web Service*. Render will build and deploy automatically on every push to `main`.

> **Tip:** Render's free tier spins down after inactivity. The first request after idle may take ~30 s. Upgrade to a paid instance type to avoid cold starts in production.

---

## Docker

Build and run locally with Docker:

```bash
docker build -t interview-coach .
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e ALLOWED_ORIGINS=http://localhost:8000 \
  interview-coach
```

> **AWS App Runner alternative:** The same `Dockerfile` can be deployed directly via [AWS App Runner](https://aws.amazon.com/apprunner/). Push the image to ECR, create an App Runner service pointing to it, and inject `ANTHROPIC_API_KEY` + `ALLOWED_ORIGINS` as App Runner environment variables. App Runner auto-scales and handles TLS termination out of the box — a strong production alternative to Render.

---

## Project Structure

```
my-interview-bot/
├── main.py              # FastAPI app — routes, Pydantic models, LLM calls
├── templates/
│   └── index.html       # Single-page frontend (Tailwind CDN + vanilla JS)
├── static/              # Optional: extra JS/CSS assets
├── requirements.txt
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
