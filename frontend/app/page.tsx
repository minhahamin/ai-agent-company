"use client";
import { useEffect, useState } from "react";
import "./globals.css";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Agent = { id: string; name: string; emoji: string; description: string };
type Event = { agent: string; name: string; output: string; step: number };
type Task = { id: string; goal: string; status: string; events: Event[]; final_report: string; approved: boolean };

export default function Page() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [goal, setGoal] = useState("우리 회사 신입 온보딩 가이드 만들기");
  const [loading, setLoading] = useState(false);
  const [task, setTask] = useState<Task | null>(null);
  const [active, setActive] = useState(0);
  const [health, setHealth] = useState("");

  useEffect(() => {
    fetch(`${API}/api/agents`).then((r) => r.json()).then(setAgents).catch(() => {});
    fetch(`${API}/api/health`).then((r) => r.json()).then((h) => setHealth(`backend OK · llm=${h.llm_mode}`)).catch(() => setHealth("backend OFFLINE — `uvicorn app.main:app` 실행 필요"));
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
      setTask(data);
      setActive((data.events || []).length - 1);
    } catch (e: any) {
      alert("백엔드 연결 실패: " + e.message);
    } finally {
      setLoading(false);
    }
  }

  const ev = task?.events?.[active];

  return (
    <div className="container">
      <div className="header">
        <h1 style={{ margin: 0 }}>🏢 AI Agent Company</h1>
        <span className="badge">{health || "connecting..."}</span>
      </div>
      <p className="small">CEO → Planner → Developer → Reviewer → Reporter 순서로 LangGraph가 협업합니다. API 키 없이도 MOCK 모드로 바로 데모 가능합니다.</p>

      <div className="grid" style={{ marginTop: 16 }}>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>① 목표 입력</h3>
          <textarea rows={4} value={goal} onChange={(e) => setGoal(e.target.value)} />
          <div style={{ height: 10 }} />
          <button className="primary" onClick={run} disabled={loading}>
            {loading ? "에이전트 협업 중..." : "▶ 협업 시작"}
          </button>
          <h3>② 조직도</h3>
          {agents.map((a) => (
            <div className="agent-row" key={a.id}>
              <div className="emoji">{a.emoji}</div>
              <div>
                <b>{a.name}</b> <span className="small">({a.id})</span>
                <div className="small">{a.description}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0 }}>③ 협업 타임라인</h3>
          {!task && <p className="small">아직 실행 결과가 없습니다. 왼쪽에서 목표를 입력하고 시작하세요.</p>}
          {task && (
            <>
              <p className="small">task {task.id} · {task.approved ? "✅ 승인" : "⚠️ 조건부"} · {task.events.length} steps</p>
              <div className="tabs">
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
            </>
          )}
        </div>
      </div>
    </div>
  );
}
