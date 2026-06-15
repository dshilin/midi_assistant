from typing import Dict, Optional
from copy import deepcopy

STATE: Dict[str, dict] = {}

DEFAULT_STATE: dict = {
    "room_type": None,
    "area": None,
    "type": None,
    "color": None,
    "brand": None,
    "selected_product": None,
    "stage": "discovery",
}


def get_state(user_id: str) -> Dict:
    return deepcopy(STATE.get(user_id, DEFAULT_STATE))


def update_state(user_id: str, updates: Dict, stage: Optional[str] = None) -> Dict:
    if user_id not in STATE:
        STATE[user_id] = deepcopy(DEFAULT_STATE)

    for k, v in updates.items():
        if v is not None:
            STATE[user_id][k] = v

    if stage:
        STATE[user_id]["stage"] = stage

    return deepcopy(STATE[user_id])


def reset_state(user_id: str) -> Dict:
    STATE[user_id] = deepcopy(DEFAULT_STATE)
    return deepcopy(STATE[user_id])
