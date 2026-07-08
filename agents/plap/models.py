"""
PLAP Pydantic models — plan-level configuration data.
These are the authoritative source for what a specific plan allows.
"""

from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator




class PlanType(str, Enum):
    k401 = "401k"
    b403 = "403b"
    g457b = "457b"
    db = "DB"
    esop = "ESOP"
    sep = "SEP"
    simple = "SIMPLE"


class VestingType(str, Enum):
    immediate = "immediate"
    cliff = "cliff"
    graduated = "graduated"


class HardshipStandard(str, Enum):
    safe_harbor = "safe_harbor"
    facts_and_circumstances = "facts_and_circumstances"


class RmdStartRule(str, Enum):
    age_73 = "age_73"
    age_75 = "age_75"


class RmdCalculationMethod(str, Enum):
    uniform_lifetime = "uniform_lifetime"
    joint_life = "joint_life"


class QualifyingExpenseType(str, Enum):
    medical = "medical"
    tuition = "tuition"
    primary_home_purchase = "primary_home_purchase"
    prevent_eviction = "prevent_eviction"
    funeral = "funeral"
    casualty_loss = "casualty_loss"
    fema_disaster = "FEMA_disaster"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class MatchTier(BaseModel):
    rate: float = Field(..., description="Employer match rate for this tier (e.g. 1.0 = 100%)")
    on_first_pct: Optional[float] = None
    on_next_pct: Optional[float] = None


class MatchFormula(BaseModel):
    tiers: list[MatchTier]
    true_up: bool = False


class VestedYearBreakpoint(BaseModel):
    year: int
    pct: float


class VestingSchedule(BaseModel):
    vesting_type: VestingType
    cliff_years: Optional[int] = None
    graduated_schedule: Optional[list[VestedYearBreakpoint]] = None
    service_crediting_method: str = "hours_of_service"

    @model_validator(mode="after")
    def validate_schedule(self) -> "VestingSchedule":
        if self.vesting_type == VestingType.cliff and self.cliff_years is None:
            raise ValueError("cliff_years required for cliff vesting")
        if self.vesting_type == VestingType.graduated and not self.graduated_schedule:
            raise ValueError("graduated_schedule required for graduated vesting")
        return self

    def vesting_pct_at_years(self, years_of_service: float) -> float:
        """Return the vested % (0.0-1.0) for a participant with given years of service."""
        if self.vesting_type == VestingType.immediate:
            return 1.0
        if self.vesting_type == VestingType.cliff:
            return 1.0 if years_of_service >= self.cliff_years else 0.0
        if self.vesting_type == VestingType.graduated:
            pct = 0.0
            for bp in sorted(self.graduated_schedule, key=lambda x: x.year):
                if years_of_service >= bp.year:
                    pct = bp.pct
            return pct
        return 0.0


class LoanPolicy(BaseModel):
    loans_permitted: bool
    max_loan_amount: int = 50_000
    max_loan_pct_of_vested: float = 0.50
    min_loan_amount: int = 1_000
    max_repayment_years: int = 5
    primary_residence_extension_years: int = 15
    outstanding_loans_permitted: int = 1
    origination_fee: Decimal = Decimal("0")
    quarterly_maintenance_fee: Decimal = Decimal("0")
    cooldown_days_after_repayment: int = 0


class HardshipPolicy(BaseModel):
    hardship_permitted: bool
    hardship_standard: HardshipStandard = HardshipStandard.safe_harbor
    qualifying_expenses: list[QualifyingExpenseType] = Field(
        default_factory=lambda: list(QualifyingExpenseType)
    )
    six_month_contribution_suspension: bool = False


class DistributionOptions(BaseModel):
    in_service_age_59_5: bool = True
    normal_retirement_age: int = 65
    early_retirement_age: Optional[int] = None
    rmd_start_rule: RmdStartRule = RmdStartRule.age_73
    rmd_calculation_method: RmdCalculationMethod = RmdCalculationMethod.uniform_lifetime
    qjsa_survivor_pct: float = 0.50
    qjsa_waiver_requires_spousal_consent: bool = True


class RolloverQdroPolicy(BaseModel):
    accepts_rollover_in: bool = True
    rollover_in_sources: list[str] = Field(default_factory=lambda: ["traditional_ira", "employer_plan", "roth_401k"])
    direct_rollover_out_permitted: bool = True
    qdro_procedures_url: Optional[str] = None
    qdro_required_fields: list[str] = Field(
        default_factory=lambda: [
            "participant_name",
            "alternate_payee_name",
            "plan_name",
            "benefit_amount_or_pct",
            "payment_period",
        ]
    )


class BlackoutStatus(BaseModel):
    is_active: bool
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    reason: Optional[str] = None


class FundRecord(BaseModel):
    fund_id: str
    fund_name: str
    ticker: Optional[str] = None
    asset_class: str
    expense_ratio: float
    is_qdia: bool = False


# ---------------------------------------------------------------------------
# Top-level plan model
# ---------------------------------------------------------------------------

class PlanRecord(BaseModel):
    plan_id: str
    plan_name: str
    plan_type: PlanType
    safe_harbor: bool
    erisa_plan_number: str
    effective_date: str
    plan_year_end: str = "12/31"

    # Eligibility — ERISA § 202 / IRC § 410(a)
    # Plans may set eligibility_age lower than ERISA's maximum of 21 (e.g. 18)
    eligibility_age: int = 21
    eligibility_months_of_service: int = 12  # 0 = immediate, 12 = standard 1-year rule

    employer_match: Optional[MatchFormula] = None
    match_vesting_schedule: VestingSchedule
    loan_policy: LoanPolicy
    hardship_policy: HardshipPolicy
    distribution_options: DistributionOptions
    rollover_qdro: RolloverQdroPolicy
    blackout_status: BlackoutStatus
    fund_lineup: list[FundRecord] = Field(default_factory=list)

    snapshot_version: str = "1.0"


class PlanCapabilities(BaseModel):
    plan_id: str
    capabilities: dict[str, bool]
