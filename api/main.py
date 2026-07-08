"""
Aldergate FastAPI — Phase 4 API layer.

Run:
  source .venv/bin/activate
  uvicorn api.main:app --reload --port 8000

Endpoints:
  POST /auth/login                    — get session token
  POST /chat                          — stream crew response (SSE)
  POST /documents/upload              — upload + verify document (SSE)
  GET  /queue                         — pending review items (sponsor)
  GET  /queue/{id}                    — single entry detail (sponsor)
  GET  /queue/{id}/docs               — uploaded documents (sponsor)
  POST /queue/{id}/approve-docs       — approve documents (sponsor)
  POST /queue/{id}/approve            — approve request (sponsor)
  POST /queue/{id}/deny               — deny request (sponsor)
  GET  /admin/audit                   — FAP audit log (sponsor)
  POST /admin/blackout                — manage blackout period (sponsor)
  GET  /health                        — health check
"""

import os
import sys

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import auth
from api.routes import chat, documents, queue, admin

app = FastAPI(
    title="Aldergate ERISA API",
    version="0.4.0",
    description="ERISA-compliant 401(k) administration — Phase 4 REST API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # tighten to your UI origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/auth",      tags=["Auth"])
app.include_router(chat.router,                           tags=["Chat"])
app.include_router(documents.router, prefix="/documents", tags=["Documents"])
app.include_router(queue.router,     prefix="/queue",     tags=["Queue"])
app.include_router(admin.router,     prefix="/admin",     tags=["Admin"])


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": "0.4.0"}
