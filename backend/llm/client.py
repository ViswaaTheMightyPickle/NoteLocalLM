import logging
import httpx

from backend.core.config import get_app_config

logger = logging.getLogger(__name__)

_TIMEOUT = 120.0


def chat(
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
) -> str:
    cfg = get_app_config()
    url = f"{cfg.ollama_url}/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": 8192},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    for attempt in range(2):
        try:
            response = httpx.post(url, json=payload, timeout=_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
        except httpx.TimeoutException:
            if attempt == 0:
                logger.warning("[llm] Timeout on first attempt, retrying...")
                continue
            raise
        except Exception as e:
            logger.error(f"[llm] Error calling Ollama: {e}")
            raise
    return ""
