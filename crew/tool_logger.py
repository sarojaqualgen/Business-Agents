"""
Lightweight tool call logger — records what each tool was called with and returned.
Reset before each crew run; read after for the structured summary.

Live mode: set a callback via set_live(fn) to receive each call as it happens,
allowing real-time display while CrewAI is still running.
"""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class ToolCall:
    tool: str
    args: str        # compact human-readable args
    result: str      # compact human-readable result


_log: list[ToolCall] = []
_live_fn: Optional[Callable[[str, str, str], None]] = None


def reset() -> None:
    _log.clear()


def set_live(fn: Callable[[str, str, str], None]) -> None:
    """Set a callback that fires synchronously after each record() call."""
    global _live_fn
    _live_fn = fn


def clear_live() -> None:
    global _live_fn
    _live_fn = None


def record(tool: str, args: str, result: str) -> None:
    _log.append(ToolCall(tool=tool, args=args, result=result))
    if _live_fn:
        try:
            _live_fn(tool, args, result)
        except Exception:
            pass  # never let a display bug crash a compliance operation


def get() -> list[ToolCall]:
    return list(_log)
