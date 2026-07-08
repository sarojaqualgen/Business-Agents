"""
Participant data layer — reads from PostgreSQL via data.db.
PART-006: Gabriel Stone    — Capital One, age 61, HCE, near retirement
PART-007: Yuki Tanaka      — Prudential, age 31, 1.5yr service, cliff not met
PART-008: Amara Osei       — Capital One, age 36, primary demo participant
PART-009: Daniela Reyes    — Capital One, age 41, existing $25k loan
"""

from data.db import all_participant_ids, get_participant as _db_get_participant
from agents.paap.models import ParticipantRecord, InvestmentElection

# Session-level overrides — applied on top of DB reads for the duration of this CLI
# session. Cleared on restart. Used so that successful transactions (investment
# reallocation, deferral change) are immediately reflected without a DB write.
_election_overrides: dict[str, list[InvestmentElection]] = {}
_deferral_overrides: dict[str, dict] = {}  # {"pct": float, "type": str}


def apply_investment_override(participant_id: str, elections: list[InvestmentElection]) -> None:
    _election_overrides[participant_id] = elections


def apply_deferral_override(participant_id: str, new_deferral_pct: float, deferral_type: str | None = None) -> None:
    _deferral_overrides[participant_id] = {"pct": new_deferral_pct, "type": deferral_type}


def get_participant(participant_id: str) -> ParticipantRecord | None:
    p = _db_get_participant(participant_id)
    if p is None:
        return None
    if participant_id in _election_overrides:
        p.investment_elections = _election_overrides[participant_id]
    if participant_id in _deferral_overrides:
        override = _deferral_overrides[participant_id]
        p.current_deferral_pct = override["pct"]
        if override["type"]:
            from agents.paap.models import DeferralType
            try:
                p.deferral_type = DeferralType(override["type"])
            except ValueError:
                pass
    return p


ALL_PARTICIPANTS: dict[str, ParticipantRecord] = {}
for _pid in all_participant_ids():
    _p = get_participant(_pid)
    if _p:
        ALL_PARTICIPANTS[_pid] = _p

PART_006 = ALL_PARTICIPANTS.get("PART-006")
PART_007 = ALL_PARTICIPANTS.get("PART-007")
PART_008 = ALL_PARTICIPANTS.get("PART-008")
PART_009 = ALL_PARTICIPANTS.get("PART-009")
