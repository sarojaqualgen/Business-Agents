"""
Static reference for the 12 FAP compliance rules.
Passed as context to Haiku when answering rule questions or explaining denials.
"""

FAP_RULES = {
    1:  "Agent registration — the calling agent must be in the plan's agent registry.",
    2:  "Blackout period — no writes allowed while a blackout is active (ERISA §101(i), 30-day advance notice required).",
    3:  "Eligibility — participant must meet minimum age (21) and service (1 year) requirements (ERISA §202 / IRC §410(a)).",
    4:  "Vesting — participant can only access what they are vested in; unvested employer match cannot be withdrawn (ERISA §203).",
    5:  "Contribution limits — employee deferral cannot exceed §402(g) limit ($23,000/year); ages 60-63 may contribute extra $10,000 (SECURE 2.0); HCEs earning >$145k must designate catch-up contributions as Roth (SECURE 2.0 §603, effective 2026).",
    6:  "RMD notice — participant past RMD age must take their required minimum distribution before any other transaction (IRC §401(a)(9)).",
    7:  "Loan cap — maximum loan is the lesser of $50,000 minus highest loan balance in last 12 months, or 50% of vested balance (IRC §72(p)).",
    8:  "Outstanding loans — plan limits on the number of loans a participant may hold at one time.",
    9:  "Hardship criteria — the expense must qualify as a genuine hardship under the plan's standard (safe harbor or facts-and-circumstances) and IRC §401(k)(2)(B).",
    10: "QJSA — distributions for married participants require spousal consent unless the participant waives the qualified joint and survivor annuity (ERISA §205).",
    11: "In-service distribution age — participant must be at least 59½ to take an in-service withdrawal (IRC §72(t)).",
    12: "415(c) annual additions — total employer + employee contributions cannot exceed $69,000 per year (IRC §415(c)).",
}

FAP_RULES_TEXT = "\n".join(f"Rule {k}: {v}" for k, v in FAP_RULES.items())
