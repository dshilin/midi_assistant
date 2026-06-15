STATES = [
    "discovery",
    "selection",
    "calculation",
    "objection",
    "closing",
]


def next_stage(state: dict) -> str:
    stage = state.get("stage", "discovery")

    if stage == "discovery":
        if state.get("type") or state.get("color"):
            return "selection"

    if stage == "selection":
        if state.get("selected_product"):
            return "calculation"

    if stage == "calculation":
        return "closing"

    return stage
