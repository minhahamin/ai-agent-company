"""LangGraph orchestration: CEO -> Planner -> Developer -> Reviewer (-> Developer retry) -> Reporter."""
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

from .agents import ROLE_MAP
from .llm import chat, is_mock
from .tools import web_search


class CompanyState(TypedDict, total=False):
    goal: str
    ceo_output: str
    plan: str
    dev_output: str
    review: str
    report: str
    approved: bool
    revisions: int
    max_revisions: int
    log: List[Dict[str, Any]]


def _log(state: CompanyState, agent: str, output: str) -> Dict[str, Any]:
    log = list(state.get("log", []))
    log.append({"agent": agent, "output": output, "step": len(log) + 1})
    return {"log": log}


def ceo_node(state: CompanyState):
    goal = state["goal"]
    out = chat(
        f"사용자 목표: {goal}\n이 목표를 3~5개의 하위 작업으로 분해하고 담당자(Planner/Developer/Reviewer/Reporter)와 완료기준을 정하세요.",
        system=ROLE_MAP["ceo"]["system"],
    )
    if is_mock():
        out = (
            f"## CEO 지시 (목표: {goal})\n"
            "1. [Planner] 요구사항 정리 및 계획 수립\n"
            "2. [Developer] 핵심 산출물 초안 작성\n"
            "3. [Reviewer] 품질 검토 및 결함 지적\n"
            "4. [Reporter] 최종 요약 보고\n"
            f"완료기준: 산출물이 실행/검토 가능하고 보고서가 포함될 것.\n\n{out}"
        )
    upd = _log(state, "ceo", out)
    upd["ceo_output"] = out
    return upd


def planner_node(state: CompanyState):
    ctx = state.get("ceo_output", state["goal"])
    search_hint = web_search(state["goal"])
    out = chat(
        f"CEO 지시:\n{ctx}\n\n참고자료:\n{search_hint}\n\n위 내용을 구체적인 단계별 실행계획(산출물, 일정, 리스크 포함)으로 만드세요.",
        system=ROLE_MAP["planner"]["system"],
    )
    if is_mock():
        out = (
            f"## 실행 계획\n- 목표: {state['goal']}\n"
            "- Step1: 요구사항 3줄 요약\n- Step2: 산출물 구조 설계\n"
            "- Step3: 초안 작성 → 검토 → 최종 보고\n"
            f"- 리스크: 범위膨脹, 모호한 완료기준\n\n{out}"
        )
    upd = _log(state, "planner", out)
    upd["plan"] = out
    return upd


def developer_node(state: CompanyState):
    plan = state.get("plan", "")
    fb = state.get("review", "")
    prompt = f"계획:\n{plan}\n"
    if fb:
        prompt += f"\n[Reviewer 피드백 - 반드시 반영]:\n{fb}\n"
    prompt += f"\n원래 목표: {state['goal']}\n위 계획에 따라 실제 산출물을 작성하세요."
    out = chat(prompt, system=ROLE_MAP["developer"]["system"])
    if is_mock():
        rev = state.get("revisions", 0)
        out = (
            f"## 산출물 초안 (rev{rev + 1})\n목표 '{state['goal']}'에 대한 결과물:\n\n"
            "```python\n# 예시 산출물\ndef solve():\n    return 'done'\n```\n"
            "- 핵심 기능 3가지 구현/정리\n- 사용 방법 포함\n"
            + (f"\n- 반영된 피드백: {fb[:300]}\n" if fb else "")
            + f"\n{out}"
        )
    upd = _log(state, "developer", out)
    upd["dev_output"] = out
    return upd


def reviewer_node(state: CompanyState):
    dev = state.get("dev_output", "")
    out = chat(
        f"다음 산출물을 검토하세요:\n{dev}\n기준: 정확성, 완성도, 실행가능성. APPROVED 또는 NEEDS_FIX로 시작하세요.",
        system=ROLE_MAP["reviewer"]["system"],
    )
    approved = False
    if is_mock():
        # mock: 1회차는 NEEDS_FIX 유도(재작업 데모), 이후 APPROVED — 단 max_revisions=0이면 바로 승인
        rev = state.get("revisions", 0)
        max_rev = state.get("max_revisions", 1)
        if rev < max_rev and " 억지" not in state.get("goal", ""):
            out = "NEEDS_FIX: 예시 코드에 실행 예제와 예외 처리가 부족함. 사용 예시와 검증 방법을 보강하세요.\n\n" + out
        else:
            out = "APPROVED: 산출물이 완성도 기준을 충족함. 경미한 개선점은 보고서에 기재.\n\n" + out
        approved = out.startswith("APPROVED")
    else:
        approved = "APPROVED" in out[:50].upper()
    upd = _log(state, "reviewer", out)
    upd["review"] = out
    upd["approved"] = approved
    upd["revisions"] = state.get("revisions", 0) + (0 if approved else 1)
    return upd


def reporter_node(state: CompanyState):
    out = chat(
        f"목표: {state['goal']}\nCEO: {state.get('ceo_output','')[:800]}\n"
        f"계획: {state.get('plan','')[:800]}\n산출물: {state.get('dev_output','')[:1500]}\n"
        f"리뷰: {state.get('review','')[:500]}\n최종 보고서를 작성하세요.",
        system=ROLE_MAP["reporter"]["system"],
    )
    if is_mock():
        out = (
            f"## 최종 보고서 — '{state['goal']}'\n"
            f"- 승인 여부: {'✅ 승인' if state.get('approved') else '⚠️ 조건부 완료'}\n"
            f"- 산출물 요약: {state.get('dev_output','')[:200]}...\n"
            "- 다음 단계: 실제 연동(API 키 설정) 후 고도화\n\n" + out
        )
    upd = _log(state, "reporter", out)
    upd["report"] = out
    return upd


def _route_after_review(state: CompanyState) -> str:
    if state.get("approved"):
        return "reporter"
    if state.get("revisions", 0) > state.get("max_revisions", 1):
        return "reporter"
    return "developer"


def build_graph():
    g = StateGraph(CompanyState)
    g.add_node("ceo", ceo_node)
    g.add_node("planner", planner_node)
    g.add_node("developer", developer_node)
    g.add_node("reviewer", reviewer_node)
    g.add_node("reporter", reporter_node)
    g.set_entry_point("ceo")
    g.add_edge("ceo", "planner")
    g.add_edge("planner", "developer")
    g.add_edge("developer", "reviewer")
    g.add_conditional_edges("reviewer", _route_after_review, {"developer": "developer", "reporter": "reporter"})
    g.add_edge("reporter", END)
    return g.compile()


_company_app = None


def get_graph():
    global _company_app
    if _company_app is None:
        _company_app = build_graph()
    return _company_app


def run_company(goal: str, max_revisions: int = 1) -> Dict[str, Any]:
    app = get_graph()
    init: CompanyState = {
        "goal": goal,
        "revisions": 0,
        "max_revisions": max_revisions,
        "log": [],
        "approved": False,
    }
    final = app.invoke(init)
    return final
