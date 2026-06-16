from loguru import logger

STATES = [
    "discovery",
    "selection",
    "calculation",
    "objection",
    "closing",
]


def next_stage(state: dict) -> str:
    current = state.get("stage", "discovery")

    if current == "discovery":
        if state.get("type") or state.get("color"):
            logger.debug("fsm discovery → selection (type={}, color={})",
                         state.get("type"), state.get("color"))
            return "selection"

    elif current == "selection":
        if state.get("selected_product"):
            logger.debug("fsm selection → calculation (product={})",
                         state.get("selected_product"))
            return "calculation"

    # calculation and closing stay as-is until explicit change
    return current
