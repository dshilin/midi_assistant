import json
from typing import Dict
from loguru import logger
from app.llm import llm_complete

EXTRACT_PROMPT = """Ты анализируешь сообщение пользователя и извлекаешь параметры напольного покрытия.

Ниже указаны УЖЕ ИЗВЕСТНЫЕ параметры (из предыдущих сообщений). 
Если пользователь в новом сообщении НЕ меняет и НЕ отменяет их — верни их как есть.
Если пользователь уточняет или меняет параметр — верни новое значение.
Если параметр никогда не упоминался — null.

Верни ТОЛЬКО JSON объект:
{{
  "type": тип напольного покрытия (ламинат, винил, SPC, паркет, ковролин и т.д.) или null,
  "color": предпочитаемый цвет или null,
  "area": площадь помещения в м2 (только число) или null,
  "room_type": тип помещения (гостиная, спальня, кухня, ванная, коридор, офис и т.д.) или null,
  "brand": предпочитаемый бренд или null
}}

Не добавляй лишнего текста."""


async def extract_entities(message: str, current_state: Dict = None) -> Dict:
    logger.debug("extract msg_len={} msg_preview={}...", len(message), message[:60])
    context = ""
    if current_state:
        known = {k: v for k, v in current_state.items() if v is not None and k != "stage"}
        if known:
            context = f"УЖЕ ИЗВЕСТНО: {known}\n\n"
    response = await llm_complete(f"{context}{EXTRACT_PROMPT}\n\nСообщение пользователя: {message}")

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
