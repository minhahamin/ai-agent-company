"""LangGraph orchestration: CEO -> [Planner -> Developer -> Reviewer (-> Developer retry)] -> Reporter.

The CEO picks which optional roles are needed; the rest are skipped."""
import re
from typing import TypedDict, List, Dict, Any
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.types import Command, interrupt

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
    roles: List[str]
    interactive: bool
    human_feedback: str
    revisions: int
    max_revisions: int
    log: List[Dict[str, Any]]


def _log(state: CompanyState, agent: str, output: str) -> Dict[str, Any]:
    log = list(state.get("log", []))
    log.append({"agent": agent, "output": output, "step": len(log) + 1})
    return {"log": log}


# Execution order of the optional roles. CEO always runs first, Reporter always last.
OPTIONAL_ROLES = ["planner", "developer", "reviewer"]
SEQUENCE = [*OPTIONAL_ROLES, "reporter"]


def normalize_roles(picked) -> List[str]:
    roles = [r for r in OPTIONAL_ROLES if r in {str(p).strip().lower() for p in picked}]
    if "developer" not in roles:
        roles = [r for r in roles if r != "reviewer"]  # nothing to review
    return roles


def parse_roles(text: str) -> List[str]:
    """Read the CEO's trailing 'ROLES: a, b' line. Unparseable -> all roles."""
    found = re.findall(r"ROLES\s*[:：]\s*(.+)", text, flags=re.IGNORECASE)
    if not found:
        return list(OPTIONAL_ROLES)
    picked = {t.strip().lower() for t in re.split(r"[,\s]+", found[-1]) if t.strip()}
    return normalize_roles(picked)


def _strip_roles_line(text: str) -> str:
    return re.sub(r"\n?[^\n]*ROLES\s*[:：][^\n]*", "", text, flags=re.IGNORECASE).rstrip()


def ceo_node(state: CompanyState):
    goal = state["goal"]
    fb = state.get("human_feedback", "")
    prev = (
        f"\n\n[이전 CEO 계획]\n{state.get('ceo_output', '')}\n[사용자 수정 요청 - 반드시 반영]\n{fb}\n"
        if fb
        else ""
    )
    out = chat(
        f"사용자 목표: {goal}{prev}\n이 목표를 3~5개의 하위 작업으로 분해하고 완료기준을 정하세요.\n"
        "그리고 이 목표에 꼭 필요한 역할만 골라, 마지막 줄에 정확히 `ROLES: planner, developer, reviewer` 형식으로 적으세요 "
        "(선택지: planner, developer, reviewer. 불필요한 역할은 빼세요. 예: 코드/문서 산출물이 필요 없으면 developer와 reviewer 제외).",
        system=ROLE_MAP["ceo"]["system"],
    )
    roles = parse_roles(out)
    out = _strip_roles_line(out)
    if is_mock():
        out = (
            f"## CEO 지시 (목표: {goal})\n"
            "1. [Planner] 요구사항 정리 및 계획 수립\n"
            "2. [Developer] 핵심 산출물 초안 작성\n"
            "3. [Reviewer] 품질 검토 및 결함 지적\n"
            "4. [Reporter] 최종 요약 보고\n"
            f"완료기준: 산출물이 실행/검토 가능하고 보고서가 포함될 것.\n\n{out}"
        )
    names = ", ".join(r.capitalize() for r in roles + ["reporter"])
    out += f"\n\n**참여 역할:** CEO, {names}"
    upd = _log(state, "ceo", out)
    upd["ceo_output"] = out
    upd["roles"] = roles
    upd["human_feedback"] = ""
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


RESPONSE_HEADING = "## 리뷰 응답"
FINAL_HEADING = "## 수정된 산출물"


def developer_node(state: CompanyState):
    plan = state.get("plan") or state.get("ceo_output", "")
    fb = state.get("review", "")
    prompt = f"계획:\n{plan}\n"
    if fb:
        prompt += (
            f"\n[Reviewer 피드백]:\n{fb}\n"
            f"\n[토론 규칙] 먼저 `{RESPONSE_HEADING}` 섹션에서 Reviewer의 지적 각각에 대해 "
            "`수용: ...`(고치겠다) 또는 `반박: ...`(근거를 들어 동의하지 않음)으로 답하세요. "
            f"그다음 `{FINAL_HEADING}` 섹션에 수용한 지적을 반영한 전체 산출물을 쓰세요.\n"
        )
    hf = state.get("human_feedback", "")
    if hf:
        prompt += f"\n[사용자 피드백 - 최우선으로 반영]:\n{hf}\n"
    prompt += f"\n원래 목표: {state['goal']}\n위 계획에 따라 실제 산출물을 작성하세요."
    out = chat(prompt, system=ROLE_MAP["developer"]["system"])
    if is_mock():
        rev = state.get("revisions", 0)
        out = (
            (f"{RESPONSE_HEADING}\n- 수용: 실행 예제와 예외 처리를 추가함\n- 반박: 없음\n\n{FINAL_HEADING}\n" if fb else "")
            + f"## 산출물 초안 (rev{rev + 1})\n목표 '{state['goal']}'에 대한 결과물:\n\n"
            "```python\n# 예시 산출물\ndef solve():\n    return 'done'\n```\n"
            "- 핵심 기능 3가지 구현/정리\n- 사용 방법 포함\n"
            + (f"\n- 반영된 피드백: {fb[:300]}\n" if fb else "")
            + f"\n{out}"
        )
    upd = _log(state, "developer", out)
    upd["dev_output"] = out
    upd["human_feedback"] = ""
    return upd


def reviewer_node(state: CompanyState):
    dev = state.get("dev_output", "")
    prompt = f"다음 산출물을 검토하세요:\n{dev}\n기준: 정확성, 완성도, 실행가능성. APPROVED 또는 NEEDS_FIX로 시작하세요."
    prev = state.get("review", "")
    if prev:
        prompt += (
            f"\n\n[당신의 이전 검토]\n{prev[:1200]}\n"
            f"위 산출물의 `{RESPONSE_HEADING}`에서 Developer가 수용/반박한 내용을 읽으세요. "
            "타당한 반박은 인정하고, 해결된 지적은 철회하세요. 아직 남은 문제만 NEEDS_FIX로 지적하세요."
        )
    out = chat(prompt, system=ROLE_MAP["reviewer"]["system"])
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


def _router(current: str):
    """Next role after `current` that the CEO selected (Reporter is always selected)."""
    def route(state: CompanyState) -> str:
        active = state.get("roles", OPTIONAL_ROLES)
        for r in SEQUENCE[SEQUENCE.index(current) + 1:] if current in SEQUENCE else SEQUENCE:
            if r == "reporter" or r in active:
                return r
        return "reporter"
    return route


def ceo_gate(state: CompanyState) -> Command:
    """Pause after the CEO's plan so the user can approve, edit roles, or ask for a revision."""
    if not state.get("interactive"):
        return Command(goto=_router("ceo")(state))
    ans = interrupt({
        "gate": "plan",
        "message": "CEO 계획을 확인하세요. 승인하거나, 참여 역할을 바꾸거나, 수정 지시를 보낼 수 있어요.",
        "roles": state.get("roles", []),
    })
    fb = (ans.get("feedback") or "").strip()
    if ans.get("action") == "revise" and fb:
        return Command(goto="ceo", update={"human_feedback": fb})
    update: Dict[str, Any] = {}
    if ans.get("roles") is not None:
        update["roles"] = normalize_roles(ans["roles"])
    return Command(goto=_router("ceo")({**state, **update}), update=update)


def review_gate(state: CompanyState) -> Command:
    """Pause after the Reviewer's verdict so the user can accept it, force a rework, or finish."""
    if not state.get("interactive"):
        return Command(goto=_route_after_review(state))
    ans = interrupt({
        "gate": "review",
        "message": "Reviewer 판정을 확인하세요. 그대로 진행하거나, 피드백과 함께 재작업시키거나, 바로 보고서로 마무리할 수 있어요.",
        "approved": bool(state.get("approved")),
    })
    action = ans.get("action")
    fb = (ans.get("feedback") or "").strip()
    if action == "revise" and fb:
        return Command(goto="developer", update={"human_feedback": fb})
    if action == "finish":
        return Command(goto="reporter")
    return Command(goto=_route_after_review(state))


def build_graph():
    g = StateGraph(CompanyState)
    g.add_node("ceo", ceo_node)
    g.add_node("planner", planner_node)
    g.add_node("developer", developer_node)
    g.add_node("reviewer", reviewer_node)
    g.add_node("reporter", reporter_node)
    g.add_node("ceo_gate", ceo_gate)
    g.add_node("review_gate", review_gate)
    g.set_entry_point("ceo")
    targets = {r: r for r in SEQUENCE}
    g.add_edge("ceo", "ceo_gate")  # ceo_gate routes onward via Command
    g.add_conditional_edges("planner", _router("planner"), targets)
    g.add_conditional_edges("developer", _router("developer"), targets)
    g.add_edge("reviewer", "review_gate")  # review_gate routes onward via Command
    g.add_edge("reporter", END)
    return g.compile(checkpointer=MemorySaver())


_company_app = None


def get_graph():
    global _company_app
    if _company_app is None:
        _company_app = build_graph()
    return _company_app


def initial_state(goal: str, max_revisions: int = 1, interactive: bool = False) -> CompanyState:
    return {
        "goal": goal,
        "revisions": 0,
        "max_revisions": max_revisions,
        "log": [],
        "approved": False,
        "interactive": interactive,
        "human_feedback": "",
    }


def run_company(goal: str, max_revisions: int = 1) -> Dict[str, Any]:
    """Blocking, non-interactive run (no pauses)."""
    import uuid

    app = get_graph()
    final = app.invoke(
        initial_state(goal, max_revisions),
        {"configurable": {"thread_id": uuid.uuid4().hex}},
    )
    return final
