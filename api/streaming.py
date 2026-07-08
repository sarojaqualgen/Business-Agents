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
            # Announce the first step immediately
            if steps:
                emit({"type": "agent_start", "agent": steps[0][0], "task": steps[0][1]})

            crew.task_callback = on_task
            result = crew.kickoff()
            emit({"type": "response", "content": str(result)})
        except Exception as exc:
            emit({"type": "error", "message": str(exc)[:600]})
        finally:
            clear_live()
            emit(None)  # sentinel — signals end of stream

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    while True:
        event = await queue.get()
        if event is None:
            yield _sse({"type": "done"})
            break
        yield _sse(event)
