# ── Use official Python slim image ────────────────────────────────────────────
FROM python:3.12-slim

# ── Set working directory ──────────────────────────────────────────────────────
WORKDIR /app

# ── Install dependencies first (cached layer) ─────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application code ──────────────────────────────────────────────────────
COPY . .

# ── Expose the port uvicorn will listen on ────────────────────────────────────
EXPOSE 8000

# ── Run the FastAPI app with uvicorn ──────────────────────────────────────────
# Use 0.0.0.0 so it's reachable from outside the container.
# ANTHROPIC_API_KEY and ALLOWED_ORIGINS must be injected as environment variables
# by the container platform (Render, AWS App Runner, Docker run -e, etc.)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
