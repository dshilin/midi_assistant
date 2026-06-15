from typing import Dict, Tuple
from loguru import logger

from app.state import get_state, update_state
from app.fsm import next_stage
from app.extractor import extract_entities
from app.prompts import build_system_prompt
from app.llm import llm_complete


async def run_fsm_agent(user_id: str, message: str) -> Tuple[str, Dict]:
    logger.info("agent user={} msg_preview={}...", user_id, message[:60])

    state = get_state(user_id)
    logger.debug("agent current_stage={}", state["stage"])

    extracted = await extract_entities(message)
    state = update_state(user_id, extracted)

    new_stage = next_stage(state)
    state = update_state(user_id, {}, stage=new_stage)

    system_prompt = build_system_prompt(state)
    logger.debug("agent system_prompt stage={}", state["stage"])

    full_prompt = f"""{system_prompt}

Сообщение пользователя: {message}

Ответь как консультант по напольным покрытиям."""

    logger.debug("agent requesting llm prompt_len={}", len(full_prompt))
    response = await llm_complete(full_prompt)

    if not response:
        logger.error("agent no response from llm user={}", user_id)
        return "Извините, произошла ошибка. Попробуйте ещё раз.", state

    logger.info("agent response user={} stage={} resp_len={}", user_id, state["stage"], len(response))
    return response, state
