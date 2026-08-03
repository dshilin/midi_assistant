from unittest.mock import AsyncMock

import pytest

from app.agent_fsm import run_fsm_agent
from app.state import reset_state, update_state


@pytest.fixture(autouse=True)
def stub_types(monkeypatch):
    """Убираем зависимость от products.db: типы ассортимента фиксированы."""
    types = lambda **kw: ["Ламинат", "Винил"]
    monkeypatch.setattr("app.agent_fsm.get_distinct_product_types", types)
    monkeypatch.setattr("app.prompts.get_distinct_product_types", types)


def _mock_llm(monkeypatch):
    """Мокаем оба LLM-вызова, возвращаем перехватчик llm_chat (для system-промпта)."""
    chat = AsyncMock(return_value="ответ")
    monkeypatch.setattr("app.agent_fsm.llm_chat", chat)
    return chat


@pytest.mark.asyncio
async def test_last_assistant_passed_from_history(monkeypatch):
    """last_assistant берётся из последней реплики ассистента в истории (фикс ①)."""
    reset_state("u1")
    from app.state import append_history

    append_history("u1", "assistant", "Здравствуйте!")
    append_history("u1", "user", "линолиум")
    append_history("u1", "assistant", "Линолеума нет. Хотите ламинат?")

    extract = AsyncMock(return_value={})
    monkeypatch.setattr("app.agent_fsm.extract_entities", extract)
    _mock_llm(monkeypatch)

    await run_fsm_agent("u1", "давай")

    assert extract.await_args.kwargs["last_assistant"] == "Линолеума нет. Хотите ламинат?"


@pytest.mark.asyncio
async def test_no_products_injects_guard_block(monkeypatch):
    """Когда товаров нет — в системный промпт уходит жёсткий запрет (фикс ②)."""
    reset_state("u2")
    update_state("u2", {"type": "линолеум"})
    update_state("u2", {}, stage="selection")

    monkeypatch.setattr("app.agent_fsm.extract_entities", AsyncMock(return_value={}))
    monkeypatch.setattr("app.agent_fsm.get_products", lambda **kw: [])
    chat = _mock_llm(monkeypatch)

    await run_fsm_agent("u2", "давай")

    system = chat.await_args.kwargs["system"]
    assert "ТОВАРОВ В БАЗЕ" in system
    assert "СТРОГО ЗАПРЕЩЕНО" in system
    assert "[указать" in system  # явный запрет заглушек
    assert "Ламинат" in system   # подсказка реально доступных типов


@pytest.mark.asyncio
async def test_found_products_are_injected_and_remembered(monkeypatch):
    """Реальные товары попадают в промпт и запоминаются в last_shown_products."""
    reset_state("u3")
    update_state("u3", {"type": "ламинат"})
    update_state("u3", {}, stage="selection")

    products = [
        {"id": 1, "name": "Ламинат A", "price": 100, "product_type": "Ламинат"},
        {"id": 2, "name": "Ламинат B", "price": 200, "product_type": "Ламинат"},
    ]
    monkeypatch.setattr("app.agent_fsm.extract_entities", AsyncMock(return_value={}))
    monkeypatch.setattr("app.agent_fsm.get_products", lambda **kw: products)
    chat = _mock_llm(monkeypatch)

    _, state = await run_fsm_agent("u3", "покажи ламинат")

    assert state["last_shown_products"] == [1, 2]
    assert "Ламинат A" in chat.await_args.kwargs["system"]


@pytest.mark.asyncio
async def test_selected_index_maps_to_product_and_advances(monkeypatch):
    """Выбор «второй» → selected_product по показанному списку, переход в calculation."""
    reset_state("u4")
    update_state("u4", {"type": "ламинат"})
    update_state("u4", {"last_shown_products": [10, 20]})
    update_state("u4", {}, stage="selection")

    by_id = {
        10: {"id": 10, "name": "Ламинат X", "price": 100},
        20: {"id": 20, "name": "Ламинат Y", "price": 150},
    }
    monkeypatch.setattr("app.agent_fsm.get_product_by_id", lambda pid, **kw: by_id.get(pid))
    monkeypatch.setattr("app.agent_fsm.get_products", lambda **kw: [])
    monkeypatch.setattr(
        "app.agent_fsm.extract_entities", AsyncMock(return_value={"selected_product_index": 2})
    )
    _mock_llm(monkeypatch)

    _, state = await run_fsm_agent("u4", "второй")

    assert state["selected_product"] == 20
    assert state["stage"] == "calculation"
