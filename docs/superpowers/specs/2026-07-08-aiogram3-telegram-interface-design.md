# aiogram3 Telegram Interface

## Goal

Add a Telegram bot interface that repeats the existing web chat behavior.
No new consultant logic is added: Telegram is only another transport for the
current FSM agent.

## Scope

Included:
- aiogram3 dependency.
- `TELEGRAM_BOT_TOKEN` in `.env.example`.
- `app/tg_bot.py` runnable as `python -m app.tg_bot`.
- `/start` greeting.
- Text messages routed to `run_fsm_agent()`.

Not included:
- Webhooks.
- Inline keyboards.
- Telegram-specific product selection logic.
- Persistent state changes.
- Changes to FastAPI `/chat` behavior.

## Architecture

Current web path:

```text
HTML chat -> FastAPI /chat -> run_fsm_agent(user_id, message)
```

New Telegram path:

```text
Telegram user -> aiogram polling -> run_fsm_agent("tg:<user_id>", text)
```

Both interfaces call the same `run_fsm_agent()` function. The `tg:` prefix
keeps Telegram user state separate from web chat state.

## Components

### `requirements.txt`

Add `aiogram>=3.0.0`.

### `.env.example`

Add:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```

### `app/tg_bot.py`

Responsibilities:
- Load `.env` with `python-dotenv`.
- Read `TELEGRAM_BOT_TOKEN`.
- Fail fast with a clear error if the token is missing.
- Create aiogram `Bot`, `Dispatcher`, and message handlers.
- Reply to `/start` with a short greeting.
- Ignore non-text messages with a short text reply.
- For text messages, call `run_fsm_agent(f"tg:{message.from_user.id}", message.text)`.
- Send the returned consultant response back to Telegram.
- Log incoming messages and handler errors.

## Data Flow

```text
Telegram text
-> aiogram message handler
-> user_id = "tg:<telegram_user_id>"
-> run_fsm_agent(user_id, text)
-> existing extractor/FSM/DB/LLM flow
-> Telegram reply
```

## Error Handling

- Missing `TELEGRAM_BOT_TOKEN`: raise a startup error before polling starts.
- Non-text message: reply that only text is supported for now.
- Agent exception: log the exception and return a generic retry message.

## Testing

Add one small test for `get_telegram_token()` or equivalent startup helper:
missing token raises a clear error, present token is returned. Also run the
existing test suite.

Manual run:

```bash
python -m app.tg_bot
```

## Deliberate Simplifications

- Polling only; add webhooks when deployment requires inbound HTTPS.
- Text only; add Telegram UI controls when product selection needs buttons.
- In-memory state remains unchanged; add persistence when sessions must survive restarts.
