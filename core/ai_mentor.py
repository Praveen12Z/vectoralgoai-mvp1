# core/ai_mentor.py
# -------------------------------------------------
# Ruthless AI Mentor (Stub – ready for OpenAI later)
# -------------------------------------------------

def get_mentor_feedback(strategy_dict: dict) -> dict:
    """
    Temporary stub.
    Later this will call OpenAI.
    """

    missing = []

    if not strategy_dict.get("risk"):
        missing.append("Risk configuration")

    exit_rules = strategy_dict.get("exit", {})
    if not exit_rules:
        missing.append("Exit rules")

    score = 100
    if missing:
        score -= 30 * len(missing)
    score = max(0, min(100, score))

    return {
        "readiness_score": score,
        "mentor_notes": [
            {
                "severity": "CRITICAL" if missing else "INFO",
                "title": "Strategy completeness check",
                "detail": (
                    "Missing critical components: "
                    + ", ".join(missing)
                    if missing
                    else "Core structure is present. Refinement needed."
                ),
            },
            {
                "severity": "WARNING",
                "title": "Market regime risk",
                "detail": "This strategy may underperform in choppy or news-driven markets.",
            },
        ],
        "missing_essentials": missing,
        "priority_fixes": [
            {
                "fix": "Define strict stop-loss logic",
                "why": "Without predefined risk, drawdowns are uncontrolled",
                "how": "Use ATR or structure-based stop-loss",
            },
            {
                "fix": "Limit over-filtering",
                "why": "Too many conditions lead to curve fitting",
                "how": "Reduce to strongest 3–4 conditions",
            },
            {
                "fix": "Add regime filter",
                "why": "Same logic fails across all regimes",
                "how": "Filter by volatility or trend strength",
            },
        ],
        "what_to_test_next": [
            "Compare RR 1:2 vs 1:3",
            "Test session-based trading only",
        ],
        "one_clarifying_question": "",
    }
