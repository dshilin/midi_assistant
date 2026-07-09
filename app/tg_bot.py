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
