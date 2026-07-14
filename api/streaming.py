"""
SSE streaming — runs a CrewAI crew in a background thread and yields
Server-Sent Events so the UI can show live thinking steps + final response.

Event types the UI receives:
  agent_start   — which agent/step is now running (show in thinking block)
  tool_use      — a tool was called (show tool name + args in thinking block)
  tool_result   — the tool returned (show result preview in thinking block)
  step_done     — a task finished (summary shown collapsed in thinking block)
  response      — the final crew output (show as the main chat bubble)
  error         — something went wrong
  done          — stream is complete
"""

import asyncio
import json
import threading
from typing import AsyncGenerator

from crew.tool_logger import reset as tl_reset, set_live, clear_live

# Step labels per principal_type — shown in the thinking block as each task runs
_STEPS: dict[str, list[tuple[str, str]]] = {
    "participant": [
        ("Intent Agent",     "Parsing your request..."),
        ("Data Agent",       "Fetching plan rules..."),
        ("Data Agent",       "Fetching your account data..."),
        ("Compliance Agent", "Running 12 ERISA compliance rules..."),
        ("Data Agent",       "Executing or queuing your transaction..."),
        ("Intent Agent",     "Composing your response..."),
    ],
    "plan_sponsor": [
        ("Intent Agent",  "Parsing your request..."),
        ("Data Agent",    "Fetching plan and queue data..."),
        ("Admin Agent",   "Processing sponsor action..."),
        ("Intent Agent",  "Composing your response..."),
    ],
    "investment_advisor": [
        ("Intent Agent",     "Parsing your recommendation..."),
        ("Data Agent",       "Fetching plan rules and fund lineup..."),
        ("Data Agent",       "Fetching participant data..."),
        ("Compliance Agent", "Running ERISA compliance check..."),
        ("Data Agent",       "Executing recommendation..."),
        ("Intent Agent",     "Composing your response..."),
    ],
    "document": [
        ("Document Agent", "Uploading and verifying document..."),
    ],
}


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def stream_crew(
    crew,
    principal_type: str = "participant",
    participant_id: str = "",
) -> AsyncGenerator[str, None]:
    """
    Run crew in a background thread; yield SSE events for every tool call,
    step completion, and the final response.
    """
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    steps = _STEPS.get(principal_type, _STEPS["participant"])
    step_idx = [0]

    def emit(data: dict | None) -> None:
        asyncio.run_coroutine_threadsafe(queue.put(data), loop)

    # Fires after every tool call via tool_logger
    def on_tool(tool: str, args: str, result: str) -> None:
        emit({"type": "tool_use",    "tool": tool, "args": args[:300]})
        emit({"type": "tool_result", "tool": tool, "preview": result[:400]})

    # Fires after every task completes
    def on_task(task_output) -> None:
        idx = step_idx[0]
        agent_name = steps[idx][0] if idx < len(steps) else "Agent"
        try:
            summary = str(task_output.raw)[:500]
        except Exception:
            summary = str(task_output)[:500]
        emit({"type": "step_done", "agent": agent_name, "summary": summary})
        step_idx[0] += 1

        # Pre-announce the next step
        next_idx = step_idx[0]
        if next_idx < len(steps):
            next_agent, next_task = steps[next_idx]
            emit({"type": "agent_start", "agent": next_agent, "task": next_task})

    def run() -> None:
        tl_reset()
        set_live(on_tool)
        try:
            # ── Pre-kickoff ────────────────────────────────────────────────────
            # Clear any supervised_pending left from a prior chat turn so stale
            # loan data never bleeds into an unrelated response (e.g. hardship).
            if participant_id:
                from crew.tools.paap_tools import clear_supervised_pending as _csp
                _csp(participant_id)

            # Snapshot queue so we can detect NEW entries added this turn.
            existing_entry_ids: set[str] = set()
            if participant_id:
                try:
                    from data.review_queue import get_all as _qa
                    existing_entry_ids = {
                        e.entry_id for e in _qa()
                        if e.participant_id == participant_id
                    }
                except Exception:
                    pass

            # Announce the first step immediately
            if steps:
                emit({"type": "agent_start", "agent": steps[0][0], "task": steps[0][1]})

            crew.task_callback = on_task
            result = crew.kickoff()

            # ── Post-kickoff: attach disposition metadata to response ──────────
            response_event: dict = {"type": "response", "content": str(result)}

            if participant_id:
                # 1. Supervised — a new supervised_pending was created this turn
                from crew.tools.paap_tools import get_supervised_pending
                pending = get_supervised_pending(participant_id)
                if pending:
                    response_event["autonomy"] = "supervised"
                    response_event["transaction"] = {
                        "action": pending["action"],
                        "payload": pending["payload"],
                        "status": "pending_confirmation",
                    }

                # 2. Human-review — a new queue entry was added this turn
                if "autonomy" not in response_event:
                    try:
                        from data.review_queue import get_all as _qa
                        new_entries = [
                            e for e in _qa()
                            if e.participant_id == participant_id
                            and e.entry_id not in existing_entry_ids
                        ]
                        if new_entries:
                            entry = new_entries[-1]
                            response_event["autonomy"] = "human_review"
                            response_event["transaction"] = {
                                "action": entry.action,
                                "entry_id": entry.entry_id,
                                "status": "queued_for_human_review",
                            }
                    except Exception:
                        pass

            emit(response_event)
        except Exception as exc:
            emit({"type": "error", "message": str(exc)[:600]})
        finally:
            clear_live()
            emit(None)  # sentinel — signals end of stream

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    async def _heartbeat() -> None:
        """Emit a keep-alive ping every 4 s so the UI spinner stays active
        while the LLM is processing between tool calls (no events fire then)."""
        try:
            while True:
                await asyncio.sleep(4)
                await queue.put({"type": "heartbeat"})
        except asyncio.CancelledError:
            pass

    heartbeat_task = asyncio.create_task(_heartbeat())
    try:
        while True:
            event = await queue.get()
            if event is None:
                yield _sse({"type": "done"})
                break
            yield _sse(event)
    finally:
        heartbeat_task.cancel()
