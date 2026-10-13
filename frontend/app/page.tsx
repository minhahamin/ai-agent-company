"use client";
import { useEffect, useState } from "react";
import "./globals.css";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Agent = { id: string; name: string; emoji: string; description: string };
type Event = { agent: string; name: string; output: string; step: number };
type Pending = { gate: "plan" | "review"; message: string; roles?: string[]; approved?: boolean };
type Task = {
  id: string; goal: string; status: string; events: Event[]; final_report: string; approved: boolean;
  interactive?: boolean; pending?: Pending | null;
};

const OPTIONAL = [
  { id: "planner", label: "🗺️ Planner" },
  { id: "developer", label: "💻 Developer" },
  { id: "reviewer", label: "🔍 Reviewer" },
];

// Defined at module scope on purpose: a component declared inside Page remounts on every keystroke.
function GatePanel({ pending, busy, onResume }: {
  pending: Pending;
  busy: boolean;
  onResume: (action: "approve" | "revise" | "finish", feedback: string, roles?: string[]) => void;
}) {
  const [feedback, setFeedback] = useState("");
  const [roles, setRoles] = useState<string[]>(pending.roles || []);
  const toggle = (id: string) => setRoles((r) => (r.includes(id) ? r.filter((x) => x !== id) : [...r, id]));
  const isPlan = pending.gate === "plan";
  return (
    <div className="gate">
      <h4>✋ {isPlan ? "계획 확인" : "판정 확인"} — 당신의 차례예요</h4>
      <p className="small">{pending.message}</p>
      {isPlan ? (
        <div className="role-pick">
          {OPTIONAL.map((o) => (
            <label key={o.id}>
              <input type="checkbox" checked={roles.includes(o.id)} onChange={() => toggle(o.id)} /> {o.label}
            </label>
          ))}
        </div>
      ) : (
        <p className="small">Reviewer 판정: {pending.approved ? "✅ 승인" : "⚠️ 수정 필요"}</p>
      )}
      <textarea rows={3} value={feedback} onChange={(e) => setFeedback(e.target.value)}
        placeholder={isPlan ? "수정 지시 (예: 범위를 줄이고 일정을 추가해줘)" : "재작업 지시 (예: 예외 처리를 추가해줘)"} />
      <div style={{ height: 8 }} />
      <div className="gate-btns">
        <button className="btn" disabled={busy} onClick={() => onResume("approve", "", isPlan ? roles : undefined)}>
          {isPlan ? "✔ 승인하고 진행" : "✔ 판정대로 진행"}
        </button>
        <button className="btn" disabled={busy || !feedback.trim()} onClick={() => onResume("revise", feedback.trim())}>
          ✎ {isPlan ? "계획 수정 요청" : "피드백으로 재작업"}
        </button>
        {!isPlan && (
          <button className="btn" disabled={busy} onClick={() => onResume("finish", "")}>🏁 바로 보고서로</button>
        )}
      </div>
    </div>
  );
}

const Win = ({ title, lav, children }: { title: string; lav?: boolean; children: React.ReactNode }) => (
  <div className={`win ${lav ? "lav" : ""}`}>
    <div className="win-bar">
      <span>{title}</span>
      <span className="win-btns"><i>_</i><i>□</i><i>×</i></span>
    </div>
    <div className="win-body">{children}</div>
  </div>
);

const AgentList = ({ agents }: { agents: Agent[] }) => (
  <>
    {agents.map((a) => (
      <div className="agent" key={a.id}>
        <div className="agent-emoji">{a.emoji}</div>
        <div className="agent-info">
          <div className="name">{a.name}</div>
          <div className="role">{a.id}</div>
        </div>
      </div>
    ))}
  </>
);

export default function Page() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [goal, setGoal] = useState("AI Agent Company: 신규 프로젝트 기획안 작성");
  const [loading, setLoading] = useState(false);
  const [task, setTask] = useState<Task | null>(null);
  const [active, setActive] = useState(0);
  const [history, setHistory] = useState<Task[]>([]);
  const [interactive, setInteractive] = useState(true);
  const [rounds, setRounds] = useState(2);

  function show(t: Task) {
    setTask(t);
    setActive((t.events || []).length - 1);
    try { localStorage.setItem("lastTaskId", t.id); } catch {}
  }

  function loadHistory() {
    fetch(`${API}/api/tasks`).then((r) => r.json()).then((list: Task[]) => setHistory([...list].reverse())).catch(() => {});
  }

  useEffect(() => {
    fetch(`${API}/api/agents`).then((r) => r.json()).then(setAgents).catch(() => {});
    loadHistory();
    try {
      const id = localStorage.getItem("lastTaskId");
      if (id) fetch(`${API}/api/tasks/${id}`).then((r) => (r.ok ? r.json() : null)).then((t) => t && show(t)).catch(() => {});
    } catch {}
  }, []);

  // While the backend works on a task, poll it; polling stops on "waiting" (our turn) or "done".
  useEffect(() => {
    if (!task || task.status !== "running") return;
    const id = task.id;
    const timer = setInterval(() => {
      fetch(`${API}/api/tasks/${id}`).then((r) => (r.ok ? r.json() : null)).then((t: Task | null) => {
        if (!t) return;
        show(t);
        if (t.status !== "running") loadHistory();
      }).catch(() => {});
    }, 1500);
    return () => clearInterval(timer);
  }, [task?.id, task?.status]);

  async function call(url: string, body: object) {
    setLoading(true);
    try {
      const r = await fetch(`${API}${url}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
      show(await r.json());
      loadHistory();
    } catch (e: any) {
      alert("요청 실패: " + e.message);
    } finally {
      setLoading(false);
    }
  }

  function run() {
    if (!goal.trim()) return;
    setTask(null);
    call("/api/tasks", { goal, max_revisions: rounds, interactive });
  }

  function resume(action: "approve" | "revise" | "finish", feedback: string, roles?: string[]) {
    if (task) call(`/api/tasks/${task.id}/resume`, { action, feedback, roles });
  }

  const busy = loading || task?.status === "running";

  const ev = task?.events?.[active];

  // "Developer (2차)": Developer/Reviewer take turns; number each one's turns so the debate reads as rounds.
  const label = (i: number) => {
    const e = task!.events[i];
    if (e.agent !== "developer" && e.agent !== "reviewer") return e.name;
    const n = task!.events.slice(0, i + 1).filter((x) => x.agent === e.agent).length;
    return n > 1 ? `${e.name} (${n}차)` : e.name;
  };

  const emojiOf = (id: string) => agents.find((a) => a.id === id)?.emoji || "✦";

  return (
    <div className="container">
      {task && (
        <article className="print-only">
          <h1>AI Agent Company 협업 보고서</h1>
          <p><b>목표:</b> {task.goal}</p>
          <p><b>Task:</b> {task.id} · {task.approved ? "승인" : "검토중"} · {task.events.length} steps</p>
          <h2>협업 타임라인</h2>
          {task.events.map((e, i) => (
            <section key={i} className="print-step">
              <h3>{i + 1}. {e.name}</h3>
              <pre>{e.output}</pre>
            </section>
          ))}
          <h2>최종 보고서</h2>
          <pre>{task.final_report}</pre>
        </article>
      )}
      <div className="screen-only">
      <span className="deco star" style={{ left: 4, top: 60, fontSize: 30 }}>★</span>
      <span className="deco star" style={{ right: 8, top: 20, fontSize: 38, animationDelay: "1s" }}>★</span>
      <span className="deco float" style={{ right: 30, top: 150, fontSize: 40 }}>☁️</span>
      <span className="deco float" style={{ left: 10, bottom: 120, fontSize: 36, animationDelay: "2s" }}>🌙</span>

      <header className="hero">
        <h1 className="title">AI Agent Company</h1>
        <p className="subtitle">목표를 입력하면 CEO가 꼭 필요한 역할만 골라 LangGraph로 협업합니다.</p>
      </header>

      <section className="stage">
        <div className="grid">
          <div className="col">
            <Win title="agents.exe">
              <AgentList agents={agents} />
            </Win>
            <Win title="history.exe" lav>
              <h4>이전 작업</h4>
              {history.length === 0 && <p className="small">아직 저장된 작업이 없어요 ♡</p>}
              <ul className="history">
                {history.slice(0, 8).map((h) => (
                  <li key={h.id} className={task?.id === h.id ? "on" : ""} onClick={() => show(h)}>
                    <span className="small">{h.id} · {h.status}</span>
                    <div>{h.goal.length > 28 ? h.goal.slice(0, 28) + "…" : h.goal}</div>
                  </li>
                ))}
              </ul>
            </Win>
          </div>

          <div className="col">
            <Win title="goal.txt - notepad">
              <h4>① 목표 입력</h4>
              <textarea rows={4} value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="예: AI Agent Company 소개 글 작성" />
              <label className="small" style={{ display: "block", marginTop: 8 }}>
                <input type="checkbox" checked={interactive} onChange={(e) => setInteractive(e.target.checked)} />{" "}
                단계별 승인 (CEO 계획 직후 · Reviewer 판정 직후에 멈춤)
              </label>
              <label className="small" style={{ display: "block", marginTop: 6 }}>
                💬 Developer ↔ Reviewer 토론 라운드{" "}
                <select value={rounds} onChange={(e) => setRounds(Number(e.target.value))}>
                  <option value={0}>없음 (1회 검토)</option>
                  <option value={1}>최대 1회 재작업</option>
                  <option value={2}>최대 2회 재작업</option>
                  <option value={3}>최대 3회 재작업</option>
                </select>
              </label>
              <div style={{ height: 12 }} />
              <button className="btn" onClick={run} disabled={busy}>
                {busy ? "에이전트 협업 중..." : "▶ 협업 시작"}
              </button>
            </Win>

            {task && (
              <Win title="timeline.log">
                <h4>② 협업 타임라인</h4>
                <ol className="timeline">
                  {task.events.map((e, i) => (
                    <li key={i} className={i === active ? "on" : ""} onClick={() => setActive(i)}>
                      <span className="tl-dot">{emojiOf(e.agent)}</span>
                      <div className="tl-body">
                        <div className="tl-head">
                          <b>{i + 1}. {label(i)}</b>
                          <span className="small">step {e.step}</span>
                        </div>
                        <div className="tl-text">{e.output.replace(/\s+/g, " ").slice(0, 90)}{e.output.length > 90 ? "…" : ""}</div>
                      </div>
                    </li>
                  ))}
                </ol>
              </Win>
            )}

            {task?.status === "waiting" && task.pending && (
              <Win title="your-turn.exe">
                <GatePanel key={`${task.id}-${task.events.length}`} pending={task.pending} busy={busy} onResume={resume} />
              </Win>
            )}

            <Win title="result.exe" lav>
              <h4>③ 협업 결과</h4>
              {!task && <p className="small">목표를 입력하고 <kbd>▶ 협업 시작</kbd>을 누르면 시작됩니다.</p>}
              {task && (
                <>
                  <p className="small">
                    task {task.id} · {task.approved ? <span className="status-indicator">승인</span> : <span className="status-indicator">검토중</span>} · {task.events.length} steps
                  </p>
                  <div className="tab-list">
                    {task.events.map((e, i) => (
                      <div key={i} className={`tab ${i === active ? "active" : ""}`} onClick={() => setActive(i)}>
                        {i + 1}. {label(i)}
                      </div>
                    ))}
                  </div>
                  {ev && (
                    <>
                      <h4>{ev.name} 출력</h4>
                      <pre className="output">{ev.output}</pre>
                    </>
                  )}
                  {task.status === "running" && <p className="small">⏳ 에이전트가 작업 중이에요…</p>}
                  {task.status === "waiting" && <p className="small">✋ your-turn 창에서 다음 단계를 정해주세요.</p>}
                  {task.status === "failed" && <p className="small">⚠️ 작업이 중단되었어요.</p>}
                  {task.final_report && (
                    <>
                      <h4>📣 최종 보고서</h4>
                      <pre className="output">{task.final_report}</pre>
                    </>
                  )}
                  {task.status === "done" && (
                    <>
                      <button className="btn" onClick={() => window.print()}>📄 보고서 PDF 다운로드</button>
                      <div style={{ height: 8 }} />
                      <a className="btn" href={`${API}/api/tasks/${task.id}/download`} style={{ display: "inline-block", textDecoration: "none" }}>📦 산출물 다운로드 (zip)</a>
                    </>
                  )}
                </>
              )}
            </Win>
          </div>
        </div>
      </section>
      </div>
    </div>
  );
}
