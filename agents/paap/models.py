"""
PAAP Pydantic models — participant account data.
PAAP is the only agent that reads and writes participant records.
Raw SSNs never appear here — only ssn_hash.
"""

from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class EmploymentStatus(str, Enum):
    active = "active"
    terminated = "terminated"
    retired = "retired"
    on_leave = "on_leave"
    military_leave = "military_leave"


class DeferralType(str, Enum):
    pre_tax = "pre_tax"
    roth = "roth"
    after_tax = "after_tax"


class AutonomyLevel(str, Enum):
    full = "full"
    supervised = "supervised"
    human_review = "human_review"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class LoanRecord(BaseModel):
    loan_id: str
    principal: Decimal
    outstanding_balance: Decimal
    interest_rate: float
    origination_date: str
    maturity_date: str
    highest_balance_last_12_months: Decimal


class InvestmentElection(BaseModel):
    fund_id: str
    allocation_pct: float


class HardshipRecord(BaseModel):
    distribution_date: str
    amount: Decimal
    expense_type: str


# ---------------------------------------------------------------------------
# Top-level participant model
# ---------------------------------------------------------------------------

class ParticipantRecord(BaseModel):
    participant_id: str
    plan_id: str
    ssn_hash: str
    date_of_birth: str
    hire_date: str
    eligibility_date: str
    employment_status: EmploymentStatus
    termination_date: Optional[str] = None
    hours_of_service_ytd: int = 0
    years_of_vesting_service: float = 0.0
    break_in_service: bool = False
    userra_military_leave: bool = False

    vested_balance: Decimal
    total_balance: Decimal
    vesting_percentage: float = Field(..., ge=0.0, le=1.0)
    employee_contributions_ytd: Decimal = Decimal("0")
    employer_contributions_ytd: Decimal = Decimal("0")
    investment_elections: list[InvestmentElection] = Field(default_factory=list)

    current_deferral_pct: float = 0.0
    deferral_type: DeferralType = DeferralType.pre_tax

    outstanding_loans: list[LoanRecord] = Field(default_factory=list)
    prior_hardship_distributions: list[HardshipRecord] = Field(default_factory=list)

    rmd_required: bool = False
    rmd_amount_current_year: Optional[Decimal] = None
    rmd_due_date: Optional[str] = None

    is_hce: bool = False
    compensation_ytd: Decimal = Decimal("0")
    age_50_or_older: bool = False
    age_60_to_63: bool = False

    @property
    def max_additional_loan_amount(self) -> Decimal:
        """IRC § 72(p): lesser of ($50,000 minus highest loan balance in last 12 months) or 50% of vested balance."""
        highest_balance = sum(
            (loan.highest_balance_last_12_months for loan in self.outstanding_loans),
            Decimal("0"),
        )
        irs_cap = Decimal("50000") - highest_balance
        pct_cap = self.vested_balance * Decimal("0.5")
        return max(Decimal("0"), min(irs_cap, pct_cap))


# ---------------------------------------------------------------------------
# Request/response models for write operations
# ---------------------------------------------------------------------------

class DeferralChangeRequest(BaseModel):
    deferral_type: DeferralType
    deferral_pct: float = Field(..., ge=0.0, le=1.0)
    effective_payroll_date: str
    fap_token: str


class InvestmentReallocationRequest(BaseModel):
    scope: str  # "future_only" | "balance_only" | "both"
    elections: list[InvestmentElection]
    fap_token: str

    @field_validator("elections")
    @classmethod
    def allocations_sum_to_one(cls, v: list[InvestmentElection]) -> list[InvestmentElection]:
        total = sum(e.allocation_pct for e in v)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Investment elections must sum to 1.0, got {total:.4f}")
        return v


class LoanRequest(BaseModel):
    amount: Decimal
    repayment_years: int
    purpose: str  # "general" | "primary_residence"
    fap_token: str


class HardshipDistributionRequest(BaseModel):
    amount: Decimal
    qualifying_expense_type: str
    documentation_refs: list[str]
    fap_token: str


class SeparationDistributionRequest(BaseModel):
    distribution_type: str  # "cash" | "direct_rollover_ira" | "direct_rollover_plan"
    rollover_destination: Optional[dict] = None
    amount: str  # "full" | "partial"
    fap_token: str


class AuditLogEntry(BaseModel):
    audit_id: str
    timestamp: str
    agent_id: str
    participant_id: str
    plan_id: str
    action: str
    input_summary: dict
    outcome: str
    fap_token_id: Optional[str] = None
