"""
POST /chat — main chatbox endpoint.

Streams SSE events so the UI can show:
  - Thinking block: which agent is running + every tool call
  - Final response: the crew's plain-English answer
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import get_session, SessionToken
from api.streaming import stream_crew
from crew.router import route

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
async def chat(req: ChatRequest, session: SessionToken = Depends(get_session)):
    crew = route(
        principal_type=session.principal_type,
        query=req.message,
        participant_id=session.participant_id or "",
        plan_id=session.plan_id or "",
        agent_id=session.agent_id,
    )

    return StreamingResponse(
        stream_crew(crew, session.principal_type, session.participant_id or ""),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
            "Connection":       "keep-alive",
        },
    )
