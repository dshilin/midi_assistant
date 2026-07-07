import json
from typing import Dict, List, Optional
from loguru import logger
from app.llm import llm_complete

EXTRACT_PROMPT = """Ты анализируешь сообщение пользователя и извлекаешь параметры напольного покрытия.

Ниже указаны УЖЕ ИЗВЕСТНЫЕ параметры (из предыдущих сообщений).
Если пользователь говорит "любой" применительно к параметру (например, "любой цвет", "любой бренд", "любой паркет" = паркет любого цвета) — убери этот параметр (верни null).
Если пользователь НЕ меняет и НЕ отменяет параметр — верни его как есть.
Если пользователь уточняет или меняет параметр — верни новое значение.
Если параметр никогда не упоминался — null.

Верни ТОЛЬКО JSON объект:
{
  "type": тип напольного покрытия (ламинат, винил, SPC, паркет, ковролин и т.д.) или null,
  "color": предпочитаемый цвет или null,
  "area": площадь помещения в м2 (только число) или null,
  "room_type": тип помещения (гостиная, спальня, кухня, ванная, коридор, офис и т.д.) или null,
  "brand": предпочитаемый бренд или null,
  "budget": бюджет на м2 в рублях (только число) или null
}

Не добавляй лишнего текста."""

EXTRACT_WITH_PRODUCTS_PROMPT = """Ты анализируешь сообщение пользователя и извлекаешь параметры напольного покрытия.

Ниже указаны УЖЕ ИЗВЕСТНЫЕ параметры (из предыдущих сообщений).
Если пользователь говорит "любой" применительно к параметру (например, "любой цвет", "любой бренд", "любой паркет" = паркет любого цвета) — убери этот параметр (верни null).
Если пользователь НЕ меняет и НЕ отменяет параметр — верни его как есть.
Если пользователь уточняет или меняет параметр — верни новое значение.
Если параметр никогда не упоминался — null.

Пользователю также были предложены товары (с номерами). Если он выбирает один из них (говорит "первый", "второй", "3", "этот", "давай", "подходит", "устраивает", "беру" или просто называет номер) — укажи его номер в selected_product_index.

Верни ТОЛЬКО JSON объект:
{
  "type": тип напольного покрытия или null,
  "color": предпочитаемый цвет или null,
  "area": площадь помещения в м2 (только число) или null,
  "room_type": тип помещения или null,
  "brand": предпочитаемый бренд или null,
  "budget": бюджет на м2 в рублях (только число) или null,
  "selected_product_index": номер выбранного товара (целое число, нумерация с 1) или null
}

Не добавляй лишнего текста."""


def _format_products_short(products: List[Dict]) -> str:
    lines = []
    for i, p in enumerate(products, 1):
        name = p.get("name", "N/A")
        price = p.get("price")
        if price:
            lines.append(f"{i}. {name} — {price} ₽")
        else:
            lines.append(f"{i}. {name}")
    return "\n".join(lines)


async def extract_entities(
    message: str,
    current_state: Optional[Dict] = None,
    products: Optional[List[Dict]] = None,
) -> Dict:
    logger.debug("extract msg_len={} msg_preview={}...", len(message), message[:60])
    internal_keys = ("stage", "selected_product", "last_shown_products")
    known = {}
    if current_state:
        known = {k: v for k, v in current_state.items() if v is not None and k not in internal_keys}
    context = f"УЖЕ ИЗВЕСТНО: {known}\n\n" if known else "УЖЕ ИЗВЕСТНО: пока ничего.\n\n"

    if products:
        block = _format_products_short(products)
        context += f"ПРЕДЛОЖЕННЫЕ ТОВАРЫ:\n{block}\n\n"
        prompt = EXTRACT_WITH_PRODUCTS_PROMPT
    else:
        prompt = EXTRACT_PROMPT

    response = await llm_complete(f"{prompt}\n\n{context}Сообщение пользователя: {message}")

    if not response:
        logger.warning("extract no response from llm")
        return {}

    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        parsed = json.loads(response[start:end])
        logger.info("extract result={}", parsed)
        return parsed
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("extract json parse error: {}", e)
        return {}
