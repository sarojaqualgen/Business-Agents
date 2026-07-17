"""
In-memory store for supervised transactions awaiting participant confirmation.

Key: participant_id
Value: { action, payload, payload_json, fap_token }

This lives in the API layer, not in crew/, because both the fast chat path
and the CrewAI path share the same pending state.
"""

_supervised_pending: dict[str, dict] = {}


def get_supervised_pending(participant_id: str) -> dict | None:
    return _supervised_pending.get(participant_id)


def set_supervised_pending(
    participant_id: str,
    action: str,
    payload: dict,
    payload_json: str,
    fap_token: str,
) -> None:
    _supervised_pending[participant_id] = {
        "action":       action,
        "payload":      payload,
        "payload_json": payload_json,
        "fap_token":    fap_token,
    }


def clear_supervised_pending(participant_id: str) -> None:
    _supervised_pending.pop(participant_id, None)
