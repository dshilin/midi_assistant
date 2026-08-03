import re
from typing import Dict, List, Optional, Tuple
from loguru import logger

from app.state import get_state, update_state, get_history, append_history, reset_state
from app.fsm import next_stage
from app.extractor import extract_entities
from app.prompts import build_system_prompt
from app.llm import llm_chat
from app.db import get_products, calculate_material, get_product_by_id, get_distinct_product_types
from app.clients import get_db_path

CRITERIA_LABELS = {
    "type": "тип",
    "color": "цвет",
    "brand": "бренд",
    "area": "площадь",
    "budget": "бюджет",
    "room_type": "помещение",
}


def _format_products(products: list) -> str:
    if not products:
        return ""

    lines = ["Доступные товары из базы (цены указаны за 1 штуку — планку/плитку):"]
    for i, p in enumerate(products, 1):
        parts = [f"{i}. {p.get('name', 'N/A')}"]
        if p.get("price"):
            parts.append(f"   Цена: {p['price']} ₽/шт")
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
        f"Цена: {price} ₽/шт",
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


def _fetch_products_by_criteria(state: Dict, db_path: str) -> List[Dict]:
    return get_products(
        product_type=state.get("type"),
        brand=state.get("brand"),
        color=state.get("color"),
        db_path=db_path,
    )


async def run_fsm_agent(user_id: str, message: str, client_slug: str = "midi") -> Tuple[str, Dict]:
    db_path = get_db_path(client_slug)
    logger.info("agent user={} msg_preview={}...", user_id, message[:60])

    state = get_state(user_id)
    logger.debug("agent current_stage={}", state["stage"])

    history = get_history(user_id)
    last_assistant = next(
        (m["content"] for m in reversed(history) if m.get("role") == "assistant"), None
    )

    # 1. Restore the product list shown on the previous turn, so the extractor
    # maps "первый/второй" onto exactly what the user saw
    shown_products: Optional[List[Dict]] = None
    if state["stage"] == "selection":
        shown_ids = state.get("last_shown_products") or []
        if shown_ids:
            shown_products = [p for p in (get_product_by_id(pid, db_path=db_path) for pid in shown_ids) if p]
        if not shown_products:
            shown_products = _fetch_products_by_criteria(state, db_path)

    # 2. Extract entities (with product context and the assistant's last reply, so a
    # short "давай" after "хотите ламинат?" is resolved into type=ламинат)
    extracted = await extract_entities(
        message, current_state=state, products=shown_products, last_assistant=last_assistant
    )

    # 3a. Restart if user agrees in closing stage
    if state.get("stage") == "closing" and extracted.get("restart"):
        logger.info("agent user requested restart")
        state = reset_state(user_id)
        response = "Начнём заново! Какое напольное покрытие вас интересует?"
        append_history(user_id, "user", message)
        append_history(user_id, "assistant", response)
        return response, state

    # 3b. Map selected_product_index → actual product ID
    selected_idx = extracted.pop("selected_product_index", None)
    if selected_idx is not None and shown_products:
        idx = int(selected_idx) - 1
        if 0 <= idx < len(shown_products):
            pid = shown_products[idx].get("id")
            if pid:
                extracted["selected_product"] = pid
                logger.info("agent user selected product id={}", pid)

    state = update_state(user_id, extracted)
    new_stage = next_stage(state)
    state = update_state(user_id, {}, stage=new_stage)

    # 4. Build context blocks for the LLM prompt
    products_block = None
    calculation_block = None

    if state["stage"] == "selection":
        # always refetch with the current criteria: the user may have just changed them
        products = _fetch_products_by_criteria(state, db_path)
        if products:
            products_block = _format_products(products)
            state = update_state(user_id, {"last_shown_products": [p["id"] for p in products if p.get("id")]})
            logger.info("agent found {} products for selection", len(products))
        else:
            state = update_state(user_id, {"last_shown_products": []})
            known = ", ".join(
                f"{label} — {state[key]}"
                for key, label in CRITERIA_LABELS.items()
                if state.get(key) not in (None, "null")
            )
            available = get_distinct_product_types(db_path=db_path)
            types_hint = f"В базе реально есть только эти типы: {', '.join(available)}." if available else ""
            products_block = (
                f"⛔ ТОВАРОВ В БАЗЕ ПО ТЕКУЩИМ КРИТЕРИЯМ НЕТ ({known}).\n"
                f"{types_hint}\n"
                "СТРОГО ЗАПРЕЩЕНО в ответе: перечислять, показывать или придумывать какие-либо товары, "
                "их цены, бренды и характеристики. Запрещены любые шаблоны и заглушки вида «[указать ...]», "
                "«бренд ...», «цена ...». Нельзя обещать список товаров, которых нет.\n"
                "Твой ответ должен: сообщить, что по этим критериям товаров нет, и предложить изменить "
                "критерии — например, выбрать один из реально доступных типов, перечисленных выше."
            )
            logger.info("agent no products for selection criteria={} available={}", known, available)

    elif state["stage"] == "calculation":
        pid = state.get("selected_product")
        area = state.get("area")
        if pid:
            product = get_product_by_id(pid, db_path=db_path)
            if product:
                calculation_block = _format_product_full(product)
                if area:
                    calc = calculate_material(area, pid, db_path=db_path)
                    if calc:
                        packs = calc['packs_needed']
                        raw_price = product.get("price")
                        price = None
                        if raw_price and str(raw_price).lower() != "null":
                            m = re.search(r'[\d.]+', str(raw_price))
                            if m:
                                price = float(m.group())
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
                        state = update_state(user_id, {"calculation_shown": True})

    # 5. Build the system prompt and dialog messages
    system_prompt = build_system_prompt(state)
    if products_block:
        system_prompt += f"\n\n{products_block}"
    if calculation_block:
        system_prompt += f"\n\n{calculation_block}"

    messages = history + [{"role": "user", "content": message}]
    logger.debug("agent requesting llm stage={} history_len={}", state["stage"], len(messages) - 1)
    response = await llm_chat(messages, system=system_prompt)

    if not response:
        logger.error("agent no response from llm user={}", user_id)
        return "Извините, произошла ошибка. Попробуйте ещё раз.", state

    # 6. Strip hallucinated dialogue (LLM sometimes writes both roles)
    for prefix in ("Пользователь:", "пользователь:", "Ассистент:", "ассистент:"):
        idx = response.find(f"\n{prefix}")
        if idx != -1:
            response = response[:idx].rstrip()
            logger.warning("agent stripped hallucinated dialogue after '{}-'", prefix.strip(":"))

    append_history(user_id, "user", message)
    append_history(user_id, "assistant", response)

    logger.info("agent response user={} stage={} resp_len={}", user_id, state["stage"], len(response))
    return response, state
