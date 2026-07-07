from typing import Dict, List, Optional
from copy import deepcopy
from loguru import logger

STATE: Dict[str, dict] = {}
HISTORY: Dict[str, List[dict]] = {}
HISTORY_LIMIT = 10  # messages (user + assistant), i.e. last 5 exchanges

DEFAULT_STATE: dict = {
    "room_type": None,
    "area": None,
    "type": None,
    "color": None,
    "brand": None,
    "budget": None,
    "selected_product": None,
    "last_shown_products": None,
    "stage": "discovery",
}


def get_state(user_id: str) -> Dict:
    state = STATE.get(user_id)
    if state is None:
        logger.debug("user={} new session, default state", user_id)
    else:
        logger.debug("user={} state stage={} type={}", user_id, state.get("stage"), state.get("type"))
    return deepcopy(state or DEFAULT_STATE)


def update_state(user_id: str, updates: Dict, stage: Optional[str] = None) -> Dict:
    if user_id not in STATE:
        STATE[user_id] = deepcopy(DEFAULT_STATE)
        logger.debug("user={} initialized session", user_id)

    for k, v in updates.items():
        if v is not None and str(v).lower() != "null":
            if k in ("area", "budget"):
                try:
                    STATE[user_id][k] = float(v)
                except (ValueError, TypeError):
                    STATE[user_id][k] = v
            else:
                STATE[user_id][k] = v

    if stage:
        old_stage = STATE[user_id]["stage"]
        STATE[user_id]["stage"] = stage
        logger.info("user={} transition {} → {}", user_id, old_stage, stage)

    if updates:
        logger.debug("user={} state updated: {}", user_id, {k: v for k, v in updates.items() if v is not None})

    return deepcopy(STATE[user_id])


def get_history(user_id: str) -> List[dict]:
    return deepcopy(HISTORY.get(user_id, []))


def append_history(user_id: str, role: str, content: str) -> None:
    HISTORY.setdefault(user_id, []).append({"role": role, "content": content})
    if len(HISTORY[user_id]) > HISTORY_LIMIT:
        HISTORY[user_id] = HISTORY[user_id][-HISTORY_LIMIT:]


def reset_state(user_id: str) -> Dict:
    logger.info("user={} resetting state", user_id)
    STATE[user_id] = deepcopy(DEFAULT_STATE)
    HISTORY.pop(user_id, None)
    return deepcopy(STATE[user_id])
