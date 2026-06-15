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
    next_s = current

    if current == "discovery":
        if state.get("type") or state.get("color"):
            next_s = "selection"

    elif current == "selection":
        if state.get("selected_product"):
            next_s = "calculation"

    elif current == "calculation":
        next_s = "closing"

    if next_s != current:
        logger.debug("fsm {} → {} (type={}, color={}, product={})",
                     current, next_s, state.get("type"), state.get("color"), state.get("selected_product"))

    return next_s
