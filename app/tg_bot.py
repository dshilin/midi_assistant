import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv
from loguru import logger

from app import clients
from app.agent_fsm import run_fsm_agent


def get_telegram_token(slug: str = "midi") -> str:
    load_dotenv()
    cfg = clients.get_client(slug)
    token = (cfg or {}).get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    return token


def client_slug_for(message: Message) -> str:
    bot = getattr(message, "bot", None)
    return getattr(bot, "client_slug", "midi")


async def handle_start(message: Message) -> None:
    await message.answer(
        "Здравствуйте! Я AI-консультант по напольным покрытиям. "
        "Напишите, что ищете: тип покрытия, цвет, помещение или площадь."
    )


async def handle_text(message: Message) -> None:
    if not message.text:
        await message.answer("Пока я понимаю только текстовые сообщения.")
        return

    slug = client_slug_for(message)
    user_id = f"tg:{slug}:{message.from_user.id}"
    logger.info("telegram client={} user={} msg_preview={}...", slug, user_id, message.text[:60])

    try:
        response, state = await run_fsm_agent(user_id, message.text, client_slug=slug)
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


def build_bots() -> list[Bot]:
    bots = []
    for slug in clients.list_clients():
        try:
            token = get_telegram_token(slug)
        except RuntimeError:
            continue
        bot = Bot(token)
        bot.client_slug = slug
        bots.append(bot)
    if not bots:
        raise RuntimeError("нет ни одного клиента с bot_token")
    return bots


async def main() -> None:
    bots = build_bots()
    dp = build_dispatcher()
    logger.info("starting telegram bot polling for {} clients", len(bots))
    await asyncio.gather(*(dp.start_polling(bot) for bot in bots))


if __name__ == "__main__":
    asyncio.run(main())
