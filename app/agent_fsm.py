from typing import Dict, List, Optional, Tuple
from loguru import logger

from app.state import get_state, update_state
from app.fsm import next_stage
from app.extractor import extract_entities
from app.prompts import build_system_prompt
from app.llm import llm_complete
from app.db import get_products, calculate_material, get_product_by_id, get_distinct_product_types


def _format_products(products: list) -> str:
    if not products:
        return ""

    lines = ["Доступные товары из базы:"]
    for i, p in enumerate(products, 1):
        parts = [f"{i}. {p.get('name', 'N/A')}"]
        if p.get("price"):
            parts.append(f"   Цена: {p['price']} ₽")
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


def _format_product_full(product: Dict) -> str:
    name = product.get("name", "N/A")
    price = product.get("price", "N/A")
    parts = [
        f"Выбранный товар: {name}",
        f"Цена: {price} ₽",
    ]
    for field, label in [
        ("product_type", "Тип"),
        ("brand", "Бренд"),
        ("collection", "Коллекция"),
        ("length_mm", "Длина"),
        ("width_mm", "Ширина"),
        ("thickness_mm", "Толщина"),
        ("wear_class", "Класс"),
        ("pieces_per_pack", "В упаковке"),
        ("area_per_pack_m2", "м²/упак"),
    ]:
        val = product.get(field)
        if val:
            parts.append(f"{label}: {val}")
    return "\n".join(parts)


async def run_fsm_agent(user_id: str, message: str) -> Tuple[str, Dict]:
    logger.info("agent user={} msg_preview={}...", user_id, message[:60])

    state = get_state(user_id)
    logger.debug("agent current_stage={}", state["stage"])

    # 1. Fetch current products if already in selection (for extractor context)
    products: Optional[List[Dict]] = None
    if state["stage"] == "selection":
        products = get_products(
            product_type=state.get("type"),
            brand=state.get("brand"),
            color=state.get("color"),
        )

    # 2. Extract entities (with product context when available)
    extracted = await extract_entities(message, current_state=state, products=products)

    # 3. Map selected_product_index → actual product ID
    selected_idx = extracted.pop("selected_product_index", None)
    if selected_idx is not None and products:
        idx = int(selected_idx) - 1
        if 0 <= idx < len(products):
            pid = products[idx].get("id")
            if pid:
                extracted["selected_product"] = pid
                logger.info("agent user selected product id={}", pid)

    state = update_state(user_id, extracted)
    new_stage = next_stage(state)
    state = update_state(user_id, {}, stage=new_stage)

    # 4. If just entered selection, fetch products now
    if state["stage"] == "selection" and not products:
        products = get_products(
            product_type=state.get("type"),
            brand=state.get("brand"),
            color=state.get("color"),
        )

    # 5. Build context blocks for the LLM prompt
    products_block = None
    calculation_block = None

    if state["stage"] == "selection":
        if products:
            products_block = _format_products(products)
            logger.info("agent found {} products for selection", len(products))
        else:
            known = {k: v for k, v in state.items() if v not in (None, "null", "selection", "objection", "calculation", "closing", "discovery") and k != "stage"}
            available = get_distinct_product_types()
            types_hint = f"В базе есть: {', '.join(available)}." if available else ""
            products_block = f"В базе нет товаров по критериям: {known}. {types_hint} Предложи клиенту расширить или изменить критерии поиска."
            logger.info("agent no products for selection criteria={} available={}", known, available)

    elif state["stage"] == "calculation":
        pid = state.get("selected_product")
        area = state.get("area")
        if pid:
            product = get_product_by_id(pid)
            if product:
                calculation_block = _format_product_full(product)
                if area:
                    calc = calculate_material(area, pid)
                    if calc:
                        packs = calc['packs_needed']
                        packs = calc['packs_needed']
                        raw_price = product.get("price")
                        price = float(raw_price) if raw_price and str(raw_price).lower() != "null" else None
                        pieces = product.get("pieces_per_pack")
                        calc_lines = [
                            f"\n\nРасчёт материалов:",
                            f"Площадь помещения: {calc['area_m2']} м²",
                            f"С запасом 10%: {calc['total_area_with_waste']} м²",
                            f"Площадь одной упаковки: {calc['area_per_pack_m2']} м²",
                            f"Нужно упаковок: {packs}",
                        ]
                        if price and pieces:
                            pp = price * pieces
                            total = pp * packs
                            calc_lines.append(f"Цена за упаковку: {pp:.0f} ₽")
                            calc_lines.append(f"Общая стоимость: {total:.0f} ₽")
                        calculation_block += "\n".join(calc_lines)

    # 6. Build full prompt
    system_prompt = build_system_prompt(state)
    logger.debug("agent system_prompt stage={}", state["stage"])

    full_prompt = system_prompt

    if products_block:
        full_prompt += f"\n\n{products_block}"
    if calculation_block:
        full_prompt += f"\n\n{calculation_block}"

    full_prompt += f"\n\n--- СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЯ ---\n{message}"

    logger.debug("agent requesting llm prompt_len={}", len(full_prompt))
    response = await llm_complete(full_prompt)

    if not response:
        logger.error("agent no response from llm user={}", user_id)
        return "Извините, произошла ошибка. Попробуйте ещё раз.", state

    logger.info("agent response user={} stage={} resp_len={}", user_id, state["stage"], len(response))
    return response, state
