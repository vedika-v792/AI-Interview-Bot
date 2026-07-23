"""
AI Interview Coach — FastAPI Backend
=====================================
Architecture: Browser → FastAPI (this file) → Groq API
The GROQ_API_KEY is held server-side only and never exposed to the client.

Stateless design: the frontend maintains conversation history and sends it
with every request. No database is used in this version (see README for
future work on Supabase/Postgres persistence).
"""

import os
import json
import re
import httpx

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

# ── Load environment variables from .env file (for local development) ──────────
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",")

# ── FastAPI app instance ───────────────────────────────────────────────────────
app = FastAPI(
    title="AI Interview Coach",
    description="A conversational AI mock-interview tool powered by Groq (Llama 3.3).",
    version="1.0.0",
)

# ── CORS middleware ────────────────────────────────────────────────────────────
# Restrict to ALLOWED_ORIGINS so the API key is only used from trusted origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Template & static file setup ──────────────────────────────────────────────
templates = Jinja2Templates(directory="templates")

# Mount the static directory only if it exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ── Groq API constants ────────────────────────────────────────────────────────
# Groq uses an OpenAI-compatible REST API with Bearer token auth.
GROQ_MODEL = "llama-3.3-70b-versatile"   # fast, free, 131k context window
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_TOKENS = 1024


# ══════════════════════════════════════════════════════════════════════════════
# Pydantic Models
# ══════════════════════════════════════════════════════════════════════════════

class HistoryItem(BaseModel):
    """A single completed Q&A pair with feedback."""
    question: str
    answer: str
    feedback: str


class StartRequest(BaseModel):
    """Request body for POST /api/start."""
    role: str


class StartResponse(BaseModel):
    """Response body for POST /api/start."""
    question: str
    question_number: int


class AnswerRequest(BaseModel):
    """Request body for POST /api/answer."""
    role: str
    question: str
    answer: str
    question_number: int           # 1-based, the question the user just answered
    history: List[HistoryItem]     # previously completed Q&A pairs (excluding current)


class AnswerResponse(BaseModel):
    """Response body for POST /api/answer."""
    feedback: str
    next_question: Optional[str] = None   # None when is_final is True
    question_number: int                  # next question number (or 5 if final)
    is_final: bool
    final_summary: Optional[str] = None   # populated only when is_final is True
    score: Optional[int] = None           # 1-10, populated only when is_final is True


# ══════════════════════════════════════════════════════════════════════════════
# LLM helper — isolated so it's easy to swap providers later
# ══════════════════════════════════════════════════════════════════════════════

async def call_llm(prompt: str) -> str:
    """
    Call the Groq API with a single user message and return the generated text.

    Groq uses an OpenAI-compatible REST API:
    - Endpoint: https://api.groq.com/openai/v1/chat/completions
    - Auth:     Authorization: Bearer {GROQ_API_KEY}
    - Response: choices[0].message.content

    Raises:
        ValueError: if the API key is missing or the response is malformed.
        httpx.HTTPStatusError: if the HTTP request fails.
    """
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is not set. Add it to your .env file or environment."
        )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(GROQ_API_URL, headers=headers, json=payload)
        if not response.is_success:
            # Log the actual Groq error to the uvicorn terminal for debugging
            print(f"[Groq API error] status={response.status_code} body={response.text[:500]}")
        response.raise_for_status()

    data = response.json()

    # Groq / OpenAI-compatible response shape: choices[0].message.content
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise ValueError(f"Unexpected Groq API response structure: {data}") from exc


# ══════════════════════════════════════════════════════════════════════════════
# Prompt builders
# ══════════════════════════════════════════════════════════════════════════════

def build_opening_prompt(role: str) -> str:
    """Prompt to generate the very first interview question."""
    return f"""You are an expert technical interviewer conducting a mock interview for a {role} position.

Ask the first interview question. Make it relevant to the {role} role — it should be a strong opening question that is open-ended, not trivially easy, and sets a professional tone.

Reply with ONLY the interview question itself. No preamble, no greetings, no labels.
"""


def build_feedback_and_next_question_prompt(
    role: str,
    question: str,
    answer: str,
    question_number: int,
    history: List[HistoryItem],
) -> str:
    """Prompt for questions 1-4: give feedback then ask the next question."""
    history_text = ""
    if history:
        history_text = "\n\nPrevious Q&A pairs in this session:\n"
        for i, item in enumerate(history, 1):
            history_text += (
                f"\nQ{i}: {item.question}\n"
                f"A{i}: {item.answer}\n"
                f"Feedback{i}: {item.feedback}\n"
            )

    return f"""You are an expert technical interviewer for a {role} position conducting a mock interview.
{history_text}
Current question (Question {question_number} of 5):
"{question}"

Candidate's answer:
"{answer}"

Your task — respond in this EXACT JSON format (no markdown fences, just raw JSON):
{{
  "feedback": "<2-3 sentences of brief, constructive, specific feedback on the candidate's answer>",
  "next_question": "<a new, distinct interview question relevant to the {role} role that builds on the conversation so far>"
}}

Rules:
- feedback must be 2-3 sentences, honest but encouraging.
- next_question must be a complete question, not previously asked, relevant to {role}.
- Output ONLY the JSON object. No extra text before or after.
"""


def build_final_summary_prompt(
    role: str,
    question: str,
    answer: str,
    question_number: int,
    history: List[HistoryItem],
) -> str:
    """Prompt for question 5 (final): give feedback + holistic summary + score."""
    history_text = ""
    if history:
        history_text = "\n\nPrevious Q&A pairs in this session:\n"
        for i, item in enumerate(history, 1):
            history_text += (
                f"\nQ{i}: {item.question}\n"
                f"A{i}: {item.answer}\n"
                f"Feedback{i}: {item.feedback}\n"
            )

    return f"""You are an expert technical interviewer for a {role} position.

The candidate has just completed a 5-question mock interview.
{history_text}
Final question (Question 5 of 5):
"{question}"

Candidate's final answer:
"{answer}"

Your task — respond in this EXACT JSON format (no markdown fences, just raw JSON):
{{
  "feedback": "<2-3 sentences of brief, constructive feedback on this final answer>",
  "final_summary": "<A 3-4 sentence holistic summary of the candidate's overall performance across all 5 questions. Highlight their strengths and key areas to improve.>",
  "score": <integer from 1 to 10 representing overall interview performance>,
  "improvement_areas": ["<area 1>", "<area 2>", "<area 3>"]
}}

Rules:
- feedback: 2-3 sentences about the final answer specifically.
- final_summary: 3-4 sentences covering the whole interview.
- score: an integer between 1 and 10.
- improvement_areas: exactly 3 specific, actionable improvement areas.
- Output ONLY the JSON object. No extra text before or after.
"""


# ══════════════════════════════════════════════════════════════════════════════
# Route helpers
# ══════════════════════════════════════════════════════════════════════════════

def parse_llm_json(raw: str) -> dict:
    """
    Parse JSON from the LLM response, stripping any accidental markdown fences.
    Returns a dict or raises ValueError.
    """
    # Strip markdown code fences if the model adds them despite instructions
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON output: {raw[:300]}") from exc


# ══════════════════════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index(request: Request):
    """Serve the single-page frontend."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/start", response_model=StartResponse, tags=["Interview"])
async def start_interview(body: StartRequest) -> StartResponse:
    """
    Begin a new interview session.

    Calls Gemini to generate the first role-specific question.
    The frontend stores this question and will send it back in the /api/answer payload.
    """
    try:
        prompt = build_opening_prompt(body.role)
        question_text = await call_llm(prompt)
        # Clean up any stray quotes the model might add
        question_text = question_text.strip().strip('"').strip()
        return StartResponse(question=question_text, question_number=1)

    except ValueError as exc:
        # Configuration error (missing API key, bad response structure)
        raise HTTPException(status_code=500, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Upstream LLM API error: {exc.response.status_code}",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")


@app.post("/api/answer", response_model=AnswerResponse, tags=["Interview"])
async def submit_answer(body: AnswerRequest) -> AnswerResponse:
    """
    Submit the candidate's answer to the current question.

    - For questions 1-4: returns feedback and the next question.
    - For question 5 (final): returns feedback, a holistic summary, a score, and
      improvement areas embedded in the final_summary string.
    """
    is_final = body.question_number == 5

    try:
        if is_final:
            prompt = build_final_summary_prompt(
                role=body.role,
                question=body.question,
                answer=body.answer,
                question_number=body.question_number,
                history=body.history,
            )
        else:
            prompt = build_feedback_and_next_question_prompt(
                role=body.role,
                question=body.question,
                answer=body.answer,
                question_number=body.question_number,
                history=body.history,
            )

        raw = await call_llm(prompt)
        parsed = parse_llm_json(raw)

        if is_final:
            # Validate expected keys
            feedback = parsed.get("feedback", "Great effort on your final answer!")
            final_summary = parsed.get("final_summary", "You completed the interview.")
            score = int(parsed.get("score", 5))
            improvement_areas: list = parsed.get("improvement_areas", [])

            # Append improvement areas to the summary for a richer display
            if improvement_areas:
                areas_formatted = "\n".join(
                    f"• {area}" for area in improvement_areas[:3]
                )
                final_summary += f"\n\n**Key improvement areas:**\n{areas_formatted}"

            return AnswerResponse(
                feedback=feedback,
                next_question=None,
                question_number=5,
                is_final=True,
                final_summary=final_summary,
                score=max(1, min(10, score)),  # clamp to [1, 10]
            )
        else:
            feedback = parsed.get("feedback", "Good answer, keep going!")
            next_question = parsed.get(
                "next_question", "Tell me about a challenging project you've worked on."
            )
            return AnswerResponse(
                feedback=feedback,
                next_question=next_question,
                question_number=body.question_number + 1,
                is_final=False,
                final_summary=None,
                score=None,
            )

    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Upstream LLM API error: {exc.response.status_code}",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")
