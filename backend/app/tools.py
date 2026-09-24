"""Shared tools the agents can call (mock-friendly)."""
import subprocess
import sys
import tempfile
import os


def web_search(query: str, max_results: int = 3) -> str:
    """Mockable web search. Real API hook: set TAVILY_API_KEY later."""
    key = os.getenv("TAVILY_API_KEY", "")
    if key:
        try:
            import httpx

            r = httpx.post(
                "https://api.tavily.com/search",
                json={"api_key": key, "query": query, "max_results": max_results},
                timeout=15,
            )
            r.raise_for_status()
            return r.text[:3000]
        except Exception as e:
            return f"[search error] {e}"
    return (
        f"[MOCK search] '{query}'에 대한 검색 결과 {max_results}건 (요약): "
        "관련 문서·베스트프랙티스를 참고했다고 가정하고 진행합니다."
    )


def run_python(code: str, timeout: int = 10) -> str:
    """Run python snippet in a subprocess, capture output."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return out[:4000] or "[no output]"
    except Exception as e:
        return f"[exec error] {e}"


def save_text(filename: str, content: str) -> str:
    tmp = tempfile.gettempdir()
    # prevent path traversal
    safe = os.path.basename(filename)
    path = os.path.join(tmp, safe)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
