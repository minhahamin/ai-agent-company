"""Pluggable LLM with cost cascade: free OpenRouter models first,
then ultra-cheap paid fallback, then deterministic mock.

Order (LLM_MODE=auto): OPENROUTER free list -> paid fallback -> mock.
Set OPENROUTER_MODELS to override the full cascade, e.g.:
  OPENROUTER_MODELS="meta-llama/llama-3.3-70b-instruct:free,openai/gpt-4o-mini"
"""
import os

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

DEFAULT_FREE_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
]
DEFAULT_PAID_FALLBACK = "meta-llama/llama-3.1-8b-instruct"  # ~$0.02/1M tokens class

# Last model that actually answered (surfaced via /api/health).
last_model: str = ""


def get_mode() -> str:
    mode = os.getenv("LLM_MODE", "auto").lower()
    if mode in ("mock", "openai", "openrouter"):
        return mode
    if os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"):
        return "openrouter" if os.getenv("OPENROUTER_API_KEY") else "openai"
    return "mock"


def get_candidates() -> list[str]:
    """Ordered model list: free first, cheap paid last."""
    custom = os.getenv("OPENROUTER_MODELS", "").strip()
    if custom:
        return [m.strip() for m in custom.split(",") if m.strip()]
    paid = os.getenv("OPENROUTER_PAID_FALLBACK", DEFAULT_PAID_FALLBACK).strip()
    return [*DEFAULT_FREE_MODELS, paid] if paid else list(DEFAULT_FREE_MODELS)


def is_mock() -> bool:
    return get_mode() == "mock"


def _is_auth_error(msg: str) -> bool:
    m = msg.lower()
    return "401" in m or "invalid api key" in m or "unauthorized" in m or "invalid_api_key" in m


def _chat_once(model: str, prompt: str, system: str, openrouter: bool) -> str:
    from langchain_openai import ChatOpenAI

    kwargs = {"model": model, "temperature": 0.4}
    if openrouter:
        kwargs["api_key"] = os.environ["OPENROUTER_API_KEY"]
        kwargs["base_url"] = OPENROUTER_BASE_URL
    llm = ChatOpenAI(**kwargs)
    msgs = []
    if system:
        msgs.append(("system", system))
    msgs.append(("human", prompt))
    content = llm.invoke(msgs).content
    return content if isinstance(content, str) else str(content)


def chat(prompt: str, system: str = "") -> str:
    """Try free models first, fall back to cheap paid, finally mock."""
    global last_model
    if is_mock():
        return _mock_chat(prompt, system)
    mode = get_mode()
    if mode == "openai":
        models = [os.getenv("OPENAI_MODEL", "gpt-4o-mini")]
        openrouter = False
    else:
        models = get_candidates()
        openrouter = True
    errors: list[str] = []
    for model in models:
        try:
            out = _chat_once(model, prompt, system, openrouter)
            last_model = model
            return out
        except Exception as e:
            msg = str(e)[:200]
            errors.append(f"{model}: {msg}")
            if _is_auth_error(msg):
                break  # key itself is bad; other models won't help
            continue  # quota/rate-limit/404 -> try next (cheaper or paid) model
    joined = " | ".join(errors)
    return _mock_chat(prompt, system) + f"\n\n[LLM cascade exhausted: {joined}]"


def _mock_chat(prompt: str, system: str = "") -> str:
    role = system[:60].replace("\n", " ")
    snippet = prompt[:800].replace("\n", " ")
    return (
        f"[MOCK {role}...] 요청을 처리했습니다. "
        f"입력 요약: {snippet}... "
        f"(실제 LLM을 쓰려면 OPENROUTER_API_KEY 또는 OPENAI_API_KEY를 설정하세요.)"
    )
