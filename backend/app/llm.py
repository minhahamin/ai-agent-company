"""Pluggable LLM: OpenRouter / OpenAI if keys exist, else deterministic mock.

Priority: LLM_MODE explicit > OPENROUTER_API_KEY > OPENAI_API_KEY > mock.
OpenRouter uses the OpenAI-compatible endpoint, so langchain-openai works
with just a base_url override.
"""
import os

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_mode() -> str:
    mode = os.getenv("LLM_MODE", "auto").lower()
    if mode in ("mock", "openai", "openrouter"):
        return mode
    # auto
    if os.getenv("OPENROUTER_API_KEY"):
        return "openrouter"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "mock"


def get_model() -> str:
    mode = get_mode()
    if mode == "openrouter":
        return os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def is_mock() -> bool:
    return get_mode() == "mock"


def chat(prompt: str, system: str = "") -> str:
    """Single chat call. Real LLM when a key is configured, else mock template."""
    if is_mock():
        return _mock_chat(prompt, system)
    try:
        from langchain_openai import ChatOpenAI

        kwargs = {"model": get_model(), "temperature": 0.4}
        if get_mode() == "openrouter":
            kwargs["api_key"] = os.environ["OPENROUTER_API_KEY"]
            kwargs["base_url"] = OPENROUTER_BASE_URL
        llm = ChatOpenAI(**kwargs)
        msgs = []
        if system:
            msgs.append(("system", system))
        msgs.append(("human", prompt))
        content = llm.invoke(msgs).content
        return content if isinstance(content, str) else str(content)
    except Exception as e:
        # Fallback to mock so demo never crashes
        return _mock_chat(prompt, system) + f"\n\n[LLM fallback: {e}]"


def _mock_chat(prompt: str, system: str = "") -> str:
    role = system[:60].replace("\n", " ")
    snippet = prompt[:800].replace("\n", " ")
    return (
        f"[MOCK {role}...] 요청을 처리했습니다. "
        f"입력 요약: {snippet}... "
        f"(실제 LLM을 쓰려면 OPENROUTER_API_KEY 또는 OPENAI_API_KEY를 설정하세요.)"
    )
