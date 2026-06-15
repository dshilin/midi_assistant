from typing import Dict, Tuple
from loguru import logger

from app.state import get_state, update_state
from app.fsm import next_stage
from app.extractor import extract_entities
from app.prompts import build_system_prompt
from app.llm import llm_complete
from app.db import get_products


def _format_products(products: list) -> str:
    if not products:
        return ""

    lines = ["Доступные товары из базы:"]
    for i, p in enumerate(products, 1):
        parts = [f"{i}. {p.get('name', 'N/A')}"]
        if p.get("price"):
            parts.append(f"   Цена: {p['price']}")
        if p.get("product_type"):
            parts.append(f"   Тип: {p['product_type']}")
        if p.get("brand"):
            parts.append(f"   Бренд: {p['brand']}")
        if p.get("collection"):
            parts.append(f"   Коллекция: {p['collection']}")
        if p.get("length_mm") and p.get("width_mm"):
            parts.append(f"   Размер: {p['length_mm']}x{p['width_mm']}мм")
        if p.get("thickness_mm"):
            parts.append(f"   Толщина: {p['thickness_mm']}мм")
        if p.get("wear_class"):
            parts.append(f"   Класс: {p['wear_class']}")
        if p.get("pieces_per_pack"):
            parts.append(f"   В упаковке: {p['pieces_per_pack']}шт")
        if p.get("area_per_pack_m2"):
            parts.append(f"   м²/упак: {p['area_per_pack_m2']}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


async def run_fsm_agent(user_id: str, message: str) -> Tuple[str, Dict]:
    logger.info("agent user={} msg_preview={}...", user_id, message[:60])

    state = get_state(user_id)
    logger.debug("agent current_stage={}", state["stage"])

    extracted = await extract_entities(message, current_state=state)
    state = update_state(user_id, extracted)

    new_stage = next_stage(state)
    state = update_state(user_id, {}, stage=new_stage)

    if state["stage"] == "selection":
        products = get_products(
            product_type=state.get("type"),
            brand=state.get("brand"),
            color=state.get("color"),
        )
        if products:
            products_block = _format_products(products)
            logger.info("agent found {} products for selection", len(products))
        else:
            known = {k: v for k, v in state.items() if v not in (None, "null", "selection", "objection", "calculation", "closing", "discovery") and k != "stage"}
            products_block = f"В базе нет товаров по критериям: {known}. Предложи клиенту расширить или изменить критерии поиска."
            logger.info("agent no products for selection criteria={}", known)
    else:
        products_block = None

    system_prompt = build_system_prompt(state)
    logger.debug("agent system_prompt stage={}", state["stage"])

    full_prompt = f"{system_prompt}"

    if products_block:
        full_prompt += f"\n\n{products_block}"

    full_prompt += f"""

--- СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЯ ---
{message}
"""

    logger.debug("agent requesting llm prompt_len={}", len(full_prompt))
    response = await llm_complete(full_prompt)

    if not response:
        logger.error("agent no response from llm user={}", user_id)
        return "Извините, произошла ошибка. Попробуйте ещё раз.", state

    logger.info("agent response user={} stage={} resp_len={}", user_id, state["stage"], len(response))
    return response, state
