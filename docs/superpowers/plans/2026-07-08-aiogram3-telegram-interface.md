# aiogram3 Telegram Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Telegram bot interface that routes text messages through the existing FSM consultant logic.

**Architecture:** Keep Telegram as a transport-only adapter. `app/tg_bot.py` owns aiogram setup, token loading, and message handlers, while all consultant behavior stays in `app.agent_fsm.run_fsm_agent()`.

**Tech Stack:** Python 3.14, aiogram3, python-dotenv, loguru, pytest.

---

## File Structure

- Modify `requirements.txt`: add `aiogram>=3.0.0`.
- Modify `.env.example`: document `TELEGRAM_BOT_TOKEN`.
- Create `app/tg_bot.py`: Telegram polling entry point and handlers.
- Create `tests/test_tg_bot.py`: token helper tests only; no Telegram network calls.

## Task 1: Add Telegram Dependency And Env Example

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`

- [ ] **Step 1: Add aiogram to dependencies**

Change `requirements.txt` to include:

```text
requests>=2.31.0
beautifulsoup4>=4.12.0
python-dotenv>=1.0.0
loguru>=0.7.0
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
pydantic>=2.0.0
openai>=1.68.0
httpx>=0.28.0
aiogram>=3.0.0
```

- [ ] **Step 2: Document Telegram token**

Append this block to `.env.example`:

```env

# Telegram bot interface
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```

- [ ] **Step 3: Commit dependency and env docs**

Run:

```bash
git add requirements.txt .env.example
git commit -m "chore: add aiogram telegram settings"
```

Expected: commit succeeds and includes only `requirements.txt` and `.env.example`.

## Task 2: Add Token Helper With Tests

**Files:**
- Create: `app/tg_bot.py`
- Create: `tests/test_tg_bot.py`

- [ ] **Step 1: Write failing token tests**

Create `tests/test_tg_bot.py`:

```python
import pytest

from app.tg_bot import get_telegram_token


def test_get_telegram_token_returns_value(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")

    assert get_telegram_token() == "123:abc"


def test_get_telegram_token_requires_value(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        get_telegram_token()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_tg_bot.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.tg_bot'`.

- [ ] **Step 3: Add minimal token helper**

Create `app/tg_bot.py`:

```python
import os

from dotenv import load_dotenv


def get_telegram_token() -> str:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    return token
```

- [ ] **Step 4: Run token tests to verify pass**

Run:

```bash
python -m pytest tests/test_tg_bot.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit token helper**

Run:

```bash
git add app/tg_bot.py tests/test_tg_bot.py
git commit -m "test: add telegram token helper"
```

Expected: commit succeeds and includes only `app/tg_bot.py` and `tests/test_tg_bot.py`.

## Task 3: Wire aiogram Bot To Existing FSM Agent

**Files:**
- Modify: `app/tg_bot.py`
- Modify: `tests/test_tg_bot.py`

- [ ] **Step 1: Add handler tests before implementation**

Replace `tests/test_tg_bot.py` with:

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.tg_bot import get_telegram_token, handle_start, handle_text


def test_get_telegram_token_returns_value(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")

    assert get_telegram_token() == "123:abc"


def test_get_telegram_token_requires_value(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        get_telegram_token()


@pytest.mark.asyncio
async def test_handle_start_replies_with_greeting():
    message = SimpleNamespace(answer=AsyncMock())

    await handle_start(message)

    message.answer.assert_awaited_once()
    assert "Здравствуйте" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_handle_text_calls_fsm_agent(monkeypatch):
    message = SimpleNamespace(
        text="нужен светлый ламинат",
        from_user=SimpleNamespace(id=42),
        answer=AsyncMock(),
    )
    run_agent = AsyncMock(return_value=("Вот варианты", {"stage": "selection"}))
    monkeypatch.setattr("app.tg_bot.run_fsm_agent", run_agent)

    await handle_text(message)

    run_agent.assert_awaited_once_with("tg:42", "нужен светлый ламинат")
    message.answer.assert_awaited_once_with("Вот варианты")


@pytest.mark.asyncio
async def test_handle_text_replies_to_non_text():
    message = SimpleNamespace(text=None, from_user=SimpleNamespace(id=42), answer=AsyncMock())

    await handle_text(message)

    message.answer.assert_awaited_once_with("Пока я понимаю только текстовые сообщения.")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_tg_bot.py -v
```

Expected: FAIL because `handle_start` and `handle_text` are not implemented.

- [ ] **Step 3: Implement aiogram handlers and polling entry point**

Replace `app/tg_bot.py` with:

```python
import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv
from loguru import logger

from app.agent_fsm import run_fsm_agent


def get_telegram_token() -> str:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    return token


async def handle_start(message: Message) -> None:
    await message.answer(
        "Здравствуйте! Я AI-консультант по напольным покрытиям. "
        "Напишите, что ищете: тип покрытия, цвет, помещение или площадь."
    )


async def handle_text(message: Message) -> None:
    if not message.text:
        await message.answer("Пока я понимаю только текстовые сообщения.")
        return

    user_id = f"tg:{message.from_user.id}"
    logger.info("telegram message user={} msg_preview={}...", user_id, message.text[:60])

    try:
        response, state = await run_fsm_agent(user_id, message.text)
    except Exception:
        logger.exception("telegram handler failed user={}", user_id)
        await message.answer("Извините, произошла ошибка. Попробуйте ещё раз.")
        return

    logger.info("telegram response user={} stage={}", user_id, state.get("stage"))
    await message.answer(response)


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.message.register(handle_start, CommandStart())
    dp.message.register(handle_text, F.text)
    dp.message.register(handle_text)
    return dp


async def main() -> None:
    bot = Bot(get_telegram_token())
    dp = build_dispatcher()
    logger.info("starting telegram bot polling")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run Telegram tests**

Run:

```bash
python -m pytest tests/test_tg_bot.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Run full test suite**

Run:

```bash
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit bot implementation**

Run:

```bash
git add app/tg_bot.py tests/test_tg_bot.py
git commit -m "feat: add aiogram telegram bot interface"
```

Expected: commit succeeds and includes only `app/tg_bot.py` and `tests/test_tg_bot.py`.

## Final Verification

- [ ] **Step 1: Confirm working tree status**

Run:

```bash
git status --short
```

Expected: no uncommitted changes from this plan.

- [ ] **Step 2: Confirm documented manual command**

Run locally after setting a real bot token in `.env`:

```bash
python -m app.tg_bot
```

Expected: log line `starting telegram bot polling`; Telegram text messages get consultant replies through the existing FSM agent.

## Self-Review

- Spec coverage: dependency, env var, `app/tg_bot.py`, `/start`, text-to-`run_fsm_agent`, non-text reply, missing-token error, agent exception reply, and polling are all covered.
- Scope: no webhooks, no inline keyboards, no persistent state, no FastAPI changes.
- Type consistency: `get_telegram_token() -> str`, `handle_start(message) -> None`, `handle_text(message) -> None`, and `build_dispatcher() -> Dispatcher` are used consistently.
