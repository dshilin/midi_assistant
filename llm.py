import os
from typing import Optional
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

LLM_PROVIDER: str = ""


async def _llm_openai(prompt: str) -> Optional[str]:
    from openai import AsyncOpenAI
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    logger.debug("openai model={} base_url={} prompt_len={}", model, base_url, len(prompt))
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.choices[0].message.content
    logger.debug("openai response_len={}", len(content) if content else 0)
    return content


async def _llm_yandexgpt(prompt: str) -> Optional[str]:
    import httpx
    api_key = os.getenv("YC_API_KEY", "")
    folder_id = os.getenv("YC_FOLDER_ID", "")
    if not api_key or not folder_id:
        logger.warning("yandexgpt credentials missing")
        return None
    logger.debug("yandexgpt prompt_len={}", len(prompt))
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": f"gpt://{folder_id}/yandexgpt-lite/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.0,
            "maxTokens": 1000,
        },
        "messages": [
            {"role": "user", "text": prompt},
        ],
    }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.is_error:
            logger.error("yandexgpt error status={}", response.status_code)
            return None
        data = response.json()
        content = data["result"]["alternatives"][0]["message"]["text"]
        logger.debug("yandexgpt response_len={}", len(content))
        return content


async def llm_complete(prompt: str) -> Optional[str]:
    global LLM_PROVIDER
    if not LLM_PROVIDER:
        LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
        logger.info("llm provider={}", LLM_PROVIDER)
    try:
        if LLM_PROVIDER == "yandexgpt":
            return await _llm_yandexgpt(prompt)
        return await _llm_openai(prompt)
    except Exception as e:
        logger.error("llm_complete error: {}", e)
        return None
