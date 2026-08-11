from unittest.mock import AsyncMock

import pytest

from app.extractor import extract_entities


@pytest.mark.asyncio
async def test_last_assistant_is_injected_into_prompt(monkeypatch):
    """Реплика ассистента должна попадать в промпт экстрактора (фикс ①)."""
    llm = AsyncMock(return_value='{"type": "ламинат"}')
    monkeypatch.setattr("app.extractor.llm_complete", llm)

    result = await extract_entities(
        "давай",
        current_state={"stage": "selection", "type": "линолеум"},
        last_assistant="Линолеума нет. Хотите рассмотреть ламинат?",
    )

    prompt = llm.await_args.args[0]
    assert "ПОСЛЕДНЯЯ РЕПЛИКА АССИСТЕНТА:" in prompt
    assert "Хотите рассмотреть ламинат?" in prompt
    assert result["type"] == "ламинат"


@pytest.mark.asyncio
async def test_prompt_omits_assistant_block_when_absent(monkeypatch):
    """Без last_assistant блока реплики ассистента в промпте быть не должно."""
    llm = AsyncMock(return_value='{"type": null}')
    monkeypatch.setattr("app.extractor.llm_complete", llm)

    await extract_entities("привет", current_state=None)

    prompt = llm.await_args.args[0]
    assert "ПОСЛЕДНЯЯ РЕПЛИКА АССИСТЕНТА" not in prompt


@pytest.mark.asyncio
async def test_products_context_uses_with_products_prompt(monkeypatch):
    """Когда переданы товары — используется промпт с selected_product_index."""
    llm = AsyncMock(return_value='{"selected_product_index": 2, "type": null}')
    monkeypatch.setattr("app.extractor.llm_complete", llm)

    result = await extract_entities(
        "второй",
        products=[{"name": "Ламинат A", "price": 100}, {"name": "Ламинат B", "price": 200}],
    )

    prompt = llm.await_args.args[0]
    assert "ПРЕДЛОЖЕННЫЕ ТОВАРЫ:" in prompt
    assert "selected_product_index" in prompt
    assert result["selected_product_index"] == 2


@pytest.mark.asyncio
async def test_parses_json_wrapped_in_text(monkeypatch):
    """JSON, обёрнутый в лишний текст, всё равно извлекается."""
    llm = AsyncMock(return_value='Вот результат: {"type": "винил"} — готово')
    monkeypatch.setattr("app.extractor.llm_complete", llm)

    result = await extract_entities("нужен винил")

    assert result["type"] == "винил"


@pytest.mark.asyncio
async def test_rejects_inferring_type_from_color(monkeypatch):
    """«надо дуб» — только цвет, тип выдумывать запрещено (фикс ③)."""
    llm = AsyncMock(return_value='{"type": null, "color": "дуб"}')
    monkeypatch.setattr("app.extractor.llm_complete", llm)

    result = await extract_entities("надо дуб")

    prompt = llm.await_args.args[0]
    assert "ЗАПРЕЩЕНО ВЫДУМЫВАТЬ ТИП ПО КОСВЕННЫМ ПРИЗНАКАМ" in prompt
    assert result["type"] is None and result["color"] == "дуб"


@pytest.mark.asyncio
async def test_no_invent_rule_present_in_products_prompt(monkeypatch):
    """Правило не выдумывать тип есть и в промпте с товарами."""
    llm = AsyncMock(return_value='{"type": null, "selected_product_index": null}')
    monkeypatch.setattr("app.extractor.llm_complete", llm)

    await extract_entities("второй", products=[{"name": "A", "price": 1}])

    assert "ЗАПРЕЩЕНО ВЫДУМЫВАТЬ ТИП ПО КОСВЕННЫМ ПРИЗНАКАМ" in llm.await_args.args[0]


@pytest.mark.asyncio
async def test_returns_empty_on_no_llm_response(monkeypatch):
    """Нет ответа LLM → пустой словарь, без исключений."""
    monkeypatch.setattr("app.extractor.llm_complete", AsyncMock(return_value=None))

    assert await extract_entities("что угодно") == {}


@pytest.mark.asyncio
async def test_returns_empty_on_invalid_json(monkeypatch):
    """Ответ без JSON → пустой словарь."""
    monkeypatch.setattr("app.extractor.llm_complete", AsyncMock(return_value="никакого json"))

    assert await extract_entities("что угодно") == {}
