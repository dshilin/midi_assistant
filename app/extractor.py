import json
from typing import Dict
from loguru import logger
from app.llm import llm_complete

EXTRACT_PROMPT = """Извлеки параметры из сообщения пользователя.

Верни ТОЛЬКО JSON объект:
{{
  "type": тип напольного покрытия (ламинат, винил, SPC, паркет, ковролин и т.д.) или null,
  "color": предпочитаемый цвет или null,
  "area": площадь помещения в м2 (только число) или null,
  "room_type": тип помещения (гостиная, спальня, кухня, ванная, коридор, офис и т.д.) или null,
  "brand": предпочитаемый бренд или null
}}

Если данных нет — укажи null для каждого поля.
Не добавляй лишнего текста."""


async def extract_entities(message: str) -> Dict:
    logger.debug("extract msg_len={} msg_preview={}...", len(message), message[:60])
    response = await llm_complete(f"{EXTRACT_PROMPT}\n\nСообщение пользователя: {message}")

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
