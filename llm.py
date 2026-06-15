import os
from typing import Optional
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

_client: Optional[AsyncOpenAI] = None
MODEL: str = ""


def get_client() -> AsyncOpenAI:
    global _client, MODEL
    if _client is None:
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
        _client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    return _client


async def llm_complete(prompt: str) -> Optional[str]:
    try:
        client = get_client()
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    except Exception:
        return None
