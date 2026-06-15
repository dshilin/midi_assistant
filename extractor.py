import json
from typing import Dict
from llm import llm_complete

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
    response = await llm_complete(f"{EXTRACT_PROMPT}\n\nСообщение пользователя: {message}")

    if not response:
        return {}

    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        return json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        return {}
