"""
Aldergate FastAPI — Phase 4 API layer.

Run:
  source .venv/bin/activate
  uvicorn api.main:app --reload --port 8000

Endpoints:
  POST /auth/login                    — get session JWT (participant or plan_sponsor)

  POST /chat                          — send message to CrewAI crew, stream SSE events (participant)

  GET  /meta/participants             — list demo participants, no auth required
  GET  /meta/plans                    — list demo plans, no auth required
  GET  /meta/actions                  — list valid action types with example messages, no auth required

  GET  /transactions/pending          — check if a supervised transaction awaits confirmation (participant)
  POST /transactions/confirm          — confirm supervised transaction;
                                        disbursement actions (loan) → awaiting_bank_details
                                        non-disbursement actions (deferral) → executes immediately (participant)
  POST /transactions/cancel           — cancel the pending supervised transaction (participant)
  POST /transactions/disburse        — provide bank details, trigger PAAP execution (participant)
                                        no entry_id  → supervised flow (loan after confirm)
                                        with entry_id → human-review flow (hardship/in-service after sponsor approves)

  POST /documents/upload              — upload + LLM-verify supporting doc for hardship or QDRO, SSE stream (participant)

  GET  /queue                         — list all pending review entries (sponsor)
  GET  /queue/{id}                    — single entry detail (sponsor)
  GET  /queue/{id}/docs               — documents uploaded for this entry (sponsor)
  POST /queue/{id}/approve-docs       — sponsor approves the uploaded documents (sponsor)
  POST /queue/{id}/approve            — approve the request;
                                        disbursement actions → approved_awaiting_bank_details
                                        non-disbursement actions → approved immediately (sponsor)
  POST /queue/{id}/deny               — deny the request with a note (sponsor)

  GET  /admin/audit                   — full FAP audit log, every compliance decision (sponsor)
  POST /admin/blackout                — manage blackout period via SponsorCrew (sponsor)

  GET  /health                        — server status, no auth
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
from api.routes import chat, documents, queue, admin, transactions, meta

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

app.include_router(auth.router,         prefix="/auth",         tags=["Auth"])
app.include_router(meta.router,         prefix="/meta",         tags=["Meta"])
app.include_router(chat.router,                                 tags=["Chat"])
app.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])
app.include_router(documents.router,    prefix="/documents",    tags=["Documents"])
app.include_router(queue.router,        prefix="/queue",        tags=["Queue"])
app.include_router(admin.router,        prefix="/admin",        tags=["Admin"])


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": "0.4.0"}
