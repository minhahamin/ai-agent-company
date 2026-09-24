"""Pluggable LLM: OpenAI if key exists, else deterministic mock (no key needed)."""
import os

MOCK_MODE = False


def get_mode() -> str:
    mode = os.getenv("LLM_MODE", "auto").lower()
    if mode == "mock":
        return "mock"
    if mode == "openai":
        return "openai"
    # auto
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "mock"


def is_mock() -> bool:
    return get_mode() == "mock"


def chat(prompt: str, system: str = "") -> str:
    """Single chat call. Uses OpenAI via langchain-openai if available, else mock template."""
    if is_mock():
        return _mock_chat(prompt, system)
    try:
        from langchain_openai import ChatOpenAI

        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        llm = ChatOpenAI(model=model, temperature=0.4)
        msgs = []
        if system:
            msgs.append(("system", system))
        msgs.append(("human", prompt))
        return llm.invoke(msgs).content
    except Exception as e:
        # Fallback to mock so demo never crashes
        return _mock_chat(prompt, system) + f"\n\n[LLM fallback: {e}]"


def _mock_chat(prompt: str, system: str = "") -> str:
    role = system[:60].replace("\n", " ")
    snippet = prompt[:800].replace("\n", " ")
    return (
        f"[MOCK {role}...] 요청을 처리했습니다. "
        f"입력 요약: {snippet}... "
        f"(실제 LLM을 쓰려면 OPENAI_API_KEY를 .env에 설정하세요.)"
    )
