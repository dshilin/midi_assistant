# FSM AI Consultant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stateful AI consultant for building materials with FSM-controlled dialogue.

**Architecture:** Three layers — LLM (thinking), FSM (scenario control), State (memory). FastAPI serves a chat UI, `agent_fsm.py` orchestrates extraction → state update → FSM transition → LLM response per message.

**Tech Stack:** Python 3.14, FastAPI, OpenAI-compatible SDK, SQLite, pytest

---

### Task 1: Create OpenAI-compatible LLM client

**Files:**
- Create: `llm.py`
- Modify: `.env.example`

The project currently uses YandexGPT directly. We need an OpenAI-compatible client that reads provider config from `.env`.

- [ ] **Step 1: Write test**

```python
import pytest
from unittest.mock import AsyncMock, patch
from llm import llm_complete


@pytest.mark.asyncio
async def test_llm_complete_success():
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock(message=AsyncMock(content="test response"))]

    with patch("llm.openai") as mock_openai:
        mock_openai.responses = AsyncMock()
        mock_openai.responses.create = AsyncMock(return_value=mock_response)

        result = await llm_complete("test prompt")
        assert result == "test response"


@pytest.mark.asyncio
async def test_llm_complete_returns_none_on_error():
    with patch("llm.openai") as mock_openai:
        mock_openai.responses = AsyncMock()
        mock_openai.responses.create = AsyncMock(side_effect=Exception("API error"))

        result = await llm_complete("test prompt")
        assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_llm.py -v`
Expected: FAIL — `llm` module not found

- [ ] **Step 3: Write OpenAI-compatible client**

```python
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("LLM_API_KEY", ""),
    base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
)

MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


async def llm_complete(prompt: str) -> str | None:
    try:
        response = await client.responses.create(
            model=MODEL,
            input=[{"role": "user", "content": prompt}],
        )
        return response.output_text
    except Exception:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_llm.py -v`
Expected: PASS

- [ ] **Step 5: Update `.env.example`**

Replace YandexGPT vars with OpenAI-compatible:

```
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

- [ ] **Step 6: Commit**

```bash
git add llm.py test_llm.py .env.example
git commit -m "feat: add OpenAI-compatible LLM client"
```

---

### Task 2: Update extractor to use new LLM client

**Files:**
- Modify: `extractor.py`

- [ ] **Step 1: Rewrite extractor to use `llm_complete`**

Replace the import and function call:

```python
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
```

- [ ] **Step 2: Run existing tests**

Run: `pytest test_fsm.py test_parse_products.py -v`
Expected: 32 PASSED (extractor tests mock at a higher level)

- [ ] **Step 3: Commit**

```bash
git add extractor.py
git commit -m "feat: update extractor to use OpenAI-compatible LLM client"
```

---

### Task 3: Update agent_fsm to use new LLM client

**Files:**
- Modify: `agent_fsm.py`

- [ ] **Step 1: Replace YandexGPT import with `llm_complete`**

```python
from typing import Dict, Tuple

from state import get_state, update_state
from fsm import next_stage
from extractor import extract_entities
from prompts import build_system_prompt
from llm import llm_complete


async def run_fsm_agent(user_id: str, message: str) -> Tuple[str, Dict]:
    state = get_state(user_id)

    extracted = await extract_entities(message)
    state = update_state(user_id, extracted)

    new_stage = next_stage(state)
    state = update_state(user_id, {}, stage=new_stage)

    system_prompt = build_system_prompt(state)

    full_prompt = f"""{system_prompt}

Сообщение пользователя: {message}

Ответь как консультант по напольным покрытиям."""

    response = await llm_complete(full_prompt)

    return response or "Извините, произошла ошибка. Попробуйте ещё раз.", state
```

- [ ] **Step 2: Run all tests**

Run: `pytest test_fsm.py test_parse_products.py -v`
Expected: 32 PASSED

- [ ] **Step 3: Commit**

```bash
git add agent_fsm.py
git commit -m "feat: update agent_fsm to use OpenAI-compatible LLM client"
```

---

### Task 4: Add openai dependency and finalize

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add `openai` to requirements**

```
requests>=2.31.0
beautifulsoup4>=4.12.0
python-dotenv>=1.0.0
loguru>=0.7.0
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
pydantic>=2.0.0
openai>=1.68.0
```

- [ ] **Step 2: Run all tests one final time**

Run: `pytest -v`
Expected: 32+ PASSED (all tests)

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add openai dependency"
```
