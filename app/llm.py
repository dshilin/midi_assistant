import os
from typing import Dict, List, Optional
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

LLM_PROVIDER: str = ""

Message = Dict[str, str]  # {"role": "user"|"assistant", "content": str}


async def _llm_openai(messages: List[Message], system: Optional[str] = None) -> Optional[str]:
    from openai import AsyncOpenAI
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    payload: List[Message] = []
    if system:
        payload.append({"role": "system", "content": system})
    payload.extend({"role": m["role"], "content": m["content"]} for m in messages)
    logger.debug("openai model={} base_url={} messages={}", model, base_url, len(payload))
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    response = await client.chat.completions.create(
        model=model,
        messages=payload,
        temperature=0.0,
    )
    content = response.choices[0].message.content
    logger.debug("openai response_len={}", len(content) if content else 0)
    return content


async def _llm_yandexgpt(messages: List[Message], system: Optional[str] = None) -> Optional[str]:
    import httpx
    import asyncio
    api_key = os.getenv("YC_API_KEY", "")
    folder_id = os.getenv("YC_FOLDER_ID", "")
    if not api_key or not folder_id:
        logger.warning("yandexgpt credentials missing")
        return None
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload_messages = []
    if system:
        payload_messages.append({"role": "system", "text": system})
    payload_messages.extend({"role": m["role"], "text": m["content"]} for m in messages)
    logger.debug("yandexgpt messages={}", len(payload_messages))
    payload = {
        "modelUri": f"gpt://{folder_id}/yandexgpt-lite/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.0,
            "maxTokens": 1000,
        },
        "messages": payload_messages,
    }
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.is_error:
                    body = response.text[:500]
                    logger.error("yandexgpt error status={} body={}", response.status_code, body)
                    if attempt == 0:
                        await asyncio.sleep(1)
                        continue
                    return None
                content = response.json()["result"]["alternatives"][0]["message"]["text"]
                logger.debug("yandexgpt response_len={}", len(content))
                return content
        except Exception as e:
            logger.error("yandexgpt exception attempt={} error={}", attempt, e)
            if attempt == 0:
                await asyncio.sleep(1)
                continue
            return None


async def llm_chat(messages: List[Message], system: Optional[str] = None) -> Optional[str]:
    global LLM_PROVIDER
    if not LLM_PROVIDER:
        LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
        logger.info("llm provider={}", LLM_PROVIDER)
    try:
        if LLM_PROVIDER in ("yandex", "yandexgpt"):
            return await _llm_yandexgpt(messages, system)
        return await _llm_openai(messages, system)
    except Exception as e:
        logger.error("llm_chat error: {}", e)
        return None


async def llm_complete(prompt: str) -> Optional[str]:
    return await llm_chat([{"role": "user", "content": prompt}])
