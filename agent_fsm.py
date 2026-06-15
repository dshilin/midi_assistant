from typing import Dict, Tuple

from state import get_state, update_state
from fsm import next_stage
from extractor import extract_entities
from prompts import build_system_prompt
from parse_products_gpt import get_yandex_gpt_response


async def run_fsm_agent(user_id: str, message: str) -> Tuple[str, Dict]:
    state = get_state(user_id)

    extracted = await extract_entities(message)
    state = update_state(user_id, extracted)

    new_stage = next_stage(state)
    state = update_state(user_id, {}, stage=new_stage)

    system_prompt = build_system_prompt(state)

    full_prompt = f"""{system_prompt}

Сообщение пользователя: {message}

Ответь как консультант по напольным покрытиям."""

    response = await get_yandex_gpt_response(full_prompt)

    return response or "Извините, произошла ошибка. Попробуйте ещё раз.", state
