"use client";
import { useEffect, useState } from "react";
import "./globals.css";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Agent = { id: string; name: string; emoji: string; description: string };
type Event = { agent: string; name: string; output: string; step: number };
type Task = { id: string; goal: string; status: string; events: Event[]; final_report: string; approved: boolean };

export default function Page() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [goal, setGoal] = useState("AI Agent Company: 신규 프로젝트 기획안 작성");
  const [loading, setLoading] = useState(false);
  const [task, setTask] = useState<Task | null>(null);
  const [active, setActive] = useState(0);
  const [history, setHistory] = useState<Task[]>([]);

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

  async function run() {
    if (!goal.trim()) return;
    setLoading(true);
    setTask(null);
    try {
      const r = await fetch(`${API}/api/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, max_revisions: 1 }),
      });
      const data = await r.json();
      show(data);
      loadHistory();
    } catch (e: any) {
      alert("백엔드 연결 실패: " + e.message);
    } finally {
      setLoading(false);
    }
  }

  const ev = task?.events?.[active];

  const Win = ({ title, lav, children }: { title: string; lav?: boolean; children: React.ReactNode }) => (
    <div className={`win ${lav ? "lav" : ""}`}>
      <div className="win-bar">
        <span>{title}</span>
        <span className="win-btns"><i>_</i><i>□</i><i>×</i></span>
      </div>
      <div className="win-body">{children}</div>
    </div>
  );

  const AgentList = () => (
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
        <p className="subtitle">목표를 입력하면 CEO·Planner·Developer·Reviewer·Reporter가 LangGraph로 협업합니다.</p>
        <span className="badge">✦ 실제 LLM 연동 ✦</span>
      </header>

      <section className="stage">
        <div className="grid">
          <div className="col">
            <Win title="agents.exe">
              <AgentList />
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
              <div style={{ height: 12 }} />
              <button className="btn" onClick={run} disabled={loading}>
                {loading ? "에이전트 협업 중..." : "▶ 협업 시작"}
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
                          <b>{i + 1}. {e.name}</b>
                          <span className="small">step {e.step}</span>
                        </div>
                        <div className="tl-text">{e.output.replace(/\s+/g, " ").slice(0, 90)}{e.output.length > 90 ? "…" : ""}</div>
                      </div>
                    </li>
                  ))}
                </ol>
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
                        {i + 1}. {e.name}
                      </div>
                    ))}
                  </div>
                  {ev && (
                    <>
                      <h4>{ev.name} 출력</h4>
                      <pre className="output">{ev.output}</pre>
                    </>
                  )}
                  <h4>📣 최종 보고서</h4>
                  <pre className="output">{task.final_report}</pre>
                  <button className="btn" onClick={() => window.print()}>📄 보고서 PDF 다운로드</button>
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
