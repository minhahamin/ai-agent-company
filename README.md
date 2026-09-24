# 🏢 AI Agent Company

> **목표 한 줄을 입력하면, 역할이 다른 5개의 AI 에이전트가 회의를 거쳐 산출물과 보고서를 만들어내는 멀티에이전트 협업 플랫폼**

예를 들어 `신입 온보딩 가이드 만들기`를 입력하면 CEO가 일을 나누고, Planner가 계획을 세우고,
Developer가 초안을 쓰고, Reviewer가 검토하고(미흡하면 재작업 지시), Reporter가 최종 보고서를 정리합니다.
전체 과정은 LangGraph 상태 그래프로 오케스트레이션되며, Next.js 대시보드에서 단계별 출력을 실시간으로 확인할 수 있습니다.

## 🌐 라이브 서비스 (Railway 배포)

| 서비스 | URL |
| --- | --- |
| 🏠 홈페이지 (Frontend) | https://ai-agent-company-production.up.railway.app |
| ⚙️ API (Backend) | https://backend-production-dc13.up.railway.app (`/api/health`로 상태 확인) |
| 🗄 DB | Railway Postgres (`tasks` 테이블에 작업 영속화) |

실모델(OpenRouter) + Postgres가 연결된 상태로 바로 시연 가능합니다.

## 📌 목차

- [라이브 서비스](#-라이브-서비스-railway-배포)

- [주요 기능](#-주요-기능)
- [기술 스택](#-기술-스택)
- [아키텍처](#-아키텍처)
- [LangGraph 워크플로우](#-langgraph-워크플로우)
- [프로젝트 구조](#-프로젝트-구조)
- [데이터 모델](#-데이터-모델)
- [로컬 실행 방법](#-로컬-실행-방법)
- [환경 변수](#-환경-변수)
- [API 명세](#-api-명세)
- [배포 (Railway)](#-배포-railway)
- [향후 개선 방향](#-향후-개선-방향)

## ✨ 주요 기능

| 기능 | 설명 |
| --- | --- |
| 역할 기반 멀티에이전트 | CEO / Planner / Developer / Reviewer / Reporter 5개 역할이 순차·조건부로 협업 |
| 자동 재작업 루프 | Reviewer가 `NEEDS_FIX`를 내리면 Developer로 회귀 (최대 재시도 횟수 설정 가능) |
| LLM 플러그인 구조 | `OPENAI_API_KEY`가 있으면 OpenAI 실모델, 없으면 MOCK 모드로 즉시 데모 가능 |
| 협업 타임라인 UI | 각 에이전트의 출력을 탭으로 탐색, 최종 보고서 하이라이트 |
| Task 영속화 | `DATABASE_URL`이 있으면 Postgres에 저장, 없으면 인메모리 저장 (로컬/배포 겸용) |
| 헬스체크 | `/api/health`에서 백엔드 상태와 현재 LLM 모드 확인 |

## 🛠 기술 스택

| 영역 | 스택 | 선정 이유 |
| --- | --- | --- |
| 프론트엔드 | Next.js 14 (App Router), React 18, TypeScript | SSR/SSG 지원, Vercel·Railway 어디서든 배포 용이 |
| 백엔드 | FastAPI, Pydantic v2 | 빠른 API 개발, 자동 타입 검증 |
| 오케스트레이션 | LangGraph (StateGraph) | 조건부 분기·재시도 루프를 그래프로 명시적 모델링 |
| LLM | langchain-openai (gpt-4o-mini 기본), MOCK 폴백 | 키 없이도 동작하는 데모 + 실서비스 전환 용이 |
| DB | PostgreSQL (SQLAlchemy 2.0) / 인메모리 폴백 | Railway Postgres 플러그인과 `DATABASE_URL` 하나로 연동 |
| 배포 | Railway (Backend + Frontend + Postgres 3개 서비스) | 모노레포를 서비스 단위로 분리 배포, 도메인 자동 발급 |
| 기타 | httpx, python-dotenv, Tavily 검색 훅(선택) | 외부 검색 API 연동 지점 분리 |

## 🏗 아키텍처

### 전체 구성도

```
                        ┌─────────────────────────────────┐
                        │        Railway Project          │
                        │       "ai-agent-company"        │
                        │                                 │
  사용자 ──▶ ┌──────────┴──────────┐   ┌──────────────────┴───────┐   ┌──────────────┐
             │  Frontend Service   │   │     Backend Service      │──▶│   Postgres   │
             │  Next.js 14         │──▶│  FastAPI + LangGraph     │   │  tasks 테이블 │
             │  (정적 빌드+서빙)    │API│  CEO→…→Reporter 그래프   │DB │              │
             └─────────────────────┘   └──────────────────────────┘   └──────────────┘
                    ▲                            ▲
                    │ 공개 도메인                 │ 공개 도메인 (NEXT_PUBLIC_API_URL)
              포트폴리오 접속                  브라우저→직접 호출 (CORS 허용)
```

### 요청 흐름 (시퀀스)

```
Browser (Next.js)        FastAPI (/api/tasks)        LangGraph          LLM/MOCK       Postgres
      │                         │                        │                 │               │
      │ POST {goal}             │                        │                 │               │
      │────────────────────────▶│ run_company()          │                 │               │
      │                         │───────────────────────▶│ ceo_node ──────────────────────▶│
      │                         │                        │ planner_node ──────────────────▶│
      │                         │                        │ developer_node ────────────────▶│
      │                         │                        │ reviewer_node ─────────────────▶│
      │                         │                        │   NEEDS_FIX? ──yes──▶ developer │
      │                         │                        │   APPROVED? ──no───▶ reporter  │
      │                         │◀── final state ────────│                 │               │
      │                         │ save_task()            │                 │               │
      │                         │────────────────────────────────────────────────────────▶│
      │◀── TaskResult ──────────│ (events + final_report)│                 │               │
```

### 핵심 설계 결정

1. **동기 실행 + 결과 반환**: 에이전트 파이프라인이 수 초 내로 끝나므로(특히 MOCK 모드),
   WebSocket/SSE 없이 `POST /api/tasks` 한 번으로 전체 협업을 실행하고 결과를 반환합니다.
   구조가 단순해 디버깅과 포트폴리오 시연에 유리합니다.
2. **LLM 추상화 (`llm.py`)**: `LLM_MODE=auto`면 키 존재 여부로 OpenRouter → OpenAI → MOCK 순으로 자동 선택합니다.
   노드 코드는 `chat(prompt, system)` 하나만 호출하므로, 모델 교체는 환경 변수만 바꾸면 됩니다.
3. **DB 이중화 (`db.py`)**: `DATABASE_URL`이 있으면 Postgres 영속화, 없으면 인메모리 dict.
   로컬에서는 설정 없이 실행되고, Railway에서는 Postgres 플러그인 연결만으로 저장소가 전환됩니다.
4. **`NEXT_PUBLIC_*` 빌드 시점 주입**: Next.js는 public 환경 변수를 빌드 타임에 고정하므로,
   배포 순서를 **Backend 먼저 → 도메인 확보 → Frontend 환경 변수 설정 → 빌드** 로 고정했습니다.

## 🔁 LangGraph 워크플로우

`backend/app/graph.py`의 `StateGraph(CompanyState)` 정의:

```
           ┌───────┐    ┌─────────┐    ┌───────────┐    ┌──────────┐    ┌──────────┐
           │  CEO  │───▶│ Planner │───▶│ Developer │───▶│ Reviewer │───▶│ Reporter │──▶ END
           └──┬────┘    └─────────┘    └─────▲─────┘    └────┬─────┘    └──────────┘
     목표 분해/분배      실행 계획 수립    산출물 작성 ▲ 재작업 │ 조건부 분기      최종 요약 보고
                                                     └──────┘
                                              NEEDS_FIX면 회귀 (revisions+1)
                                              APPROVED 또는 횟수 초과면 Reporter로
```

### 상태 (CompanyState, TypedDict)

| 필드 | 용도 |
| --- | --- |
| `goal` | 사용자 입력 목표 |
| `ceo_output` / `plan` / `dev_output` / `review` / `report` | 각 노드의 출력 (다음 노드의 컨텍스트) |
| `approved` | Reviewer 승인 여부 |
| `revisions` / `max_revisions` | 재작업 횟수 / 상한 (무한 루프 방지) |
| `log` | `{agent, output, step}` 리스트 — 타임라인 UI의 데이터 소스 |

### 에이전트 역할표 (`agents.py`)

| ID | 이름 | 책임 | 출력 형식 |
| --- | --- | --- | --- |
| `ceo` | 👔 CEO | 목표를 3~5개 하위 작업으로 분해, 담당·완료기준 지정 | 지시문 |
| `planner` | 🗺️ Planner | 실행 계획(산출물·리스크 포함), 웹검색 참고자료 활용 | 단계별 계획 |
| `developer` | 💻 Developer | 실제 산출물(코드·문서 초안) 작성, 피드백 반영 | 코드블록 포함 초안 |
| `reviewer` | 🔍 Reviewer | 품질 검토, `APPROVED` 또는 `NEEDS_FIX: <사유>` 판정 | 판정 + 사유 |
| `reporter` | 📣 Reporter | 전체 협업 요약, 다음 단계 제안 | 최종 보고서 |

에이전트 공용 도구(`tools.py`): `web_search()` (Tavily 키 있으면 실검색, 없으면 MOCK),
`run_python()` (서브프로세스 코드 실행), `save_text()` (임시 파일 저장).

## 📁 프로젝트 구조

```
ai-agent-company/
├── README.md
├── .gitignore
├── backend/
│   ├── requirements.txt        # fastapi, uvicorn, langgraph, sqlalchemy, psycopg2 등
│   ├── Procfile                # Railway/Nixpacks 시작 명령
│   ├── railway.json            # 빌더·시작 명령·헬스체크 정의
│   ├── .env.example            # OPENAI_API_KEY, DATABASE_URL 등
│   └── app/
│       ├── main.py             # FastAPI 라우트 (/api/health, /api/agents, /api/tasks)
│       ├── graph.py            # LangGraph 상태 그래프 + 5개 노드 + 조건부 라우팅
│       ├── agents.py           # 역할 정의·시스템 프롬프트
│       ├── llm.py              # OpenAI/MOCK 플러그인 LLM
│       ├── tools.py            # web_search, run_python, save_text
│       ├── db.py               # Postgres 영속화 (없으면 인메모리 폴백)
│       └── schemas.py          # Pydantic 모델 (TaskCreate, TaskResult, AgentEvent)
└── frontend/
    ├── package.json            # next 14, react 18
    ├── next.config.js
    ├── tsconfig.json
    ├── railway.json            # build/start 명령·헬스체크 정의
    ├── .env.local.example      # NEXT_PUBLIC_API_URL
    └── app/
        ├── layout.tsx
        ├── page.tsx            # 목표 입력 → 협업 실행 → 타임라인/보고서 대시보드
        └── globals.css         # 다크 테마 스타일
```

## 🗄 데이터 모델

`TaskResult` (API 응답이자 `tasks` 테이블 스키마):

```json
{
  "id": "a1b2c3d4",
  "goal": "신입 온보딩 가이드 만들기",
  "status": "done",
  "events": [{ "agent": "ceo", "name": "CEO", "status": "done", "output": "...", "step": 1 }],
  "final_report": "## 최종 보고서 ...",
  "approved": true
}
```

Postgres 테이블(`tasks`): `id PK, goal TEXT, status VARCHAR, events JSON, final_report TEXT, approved BOOL`.

## 💻 로컬 실행 방법

**1) 백엔드** (새 터미널, Windows PowerShell):

```powershell
Set-Location backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # OPENROUTER_API_KEY 넣으면 실모델, 비워두면 MOCK
uvicorn app.main:app --reload --port 8000
```

**2) 프론트엔드** (새 터미널):

```powershell
Set-Location frontend
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

→ http://localhost:3000 접속 → 목표 입력 → **▶ 협업 시작**

## 🔧 환경 변수

| 변수 | 위치 | 필수 | 설명 |
| --- | --- | --- | --- |
| `OPENROUTER_API_KEY` | backend | 선택(배포시 설정됨) | 있으면 OpenRouter 실모델, 없으면 MOCK 모드 |
| `OPENROUTER_MODEL` | backend | 선택 | 기본 `openai/gpt-4o-mini` (예: `anthropic/claude-3.5-sonnet`) |
| `OPENAI_API_KEY` | backend | 선택 | OpenRouter 키가 없을 때 직접 OpenAI 사용 |
| `OPENAI_MODEL` | backend | 선택 | 기본 `gpt-4o-mini` |
| `LLM_MODE` | backend | 선택 | `auto`(기본) / `openrouter` / `openai` / `mock` |
| `DATABASE_URL` | backend | 선택(Railway 자동주입) | 있으면 Postgres 저장, 없으면 인메모리 |
| `FRONTEND_URL` | backend | 선택 | CORS 허용 오리진 |
| `TAVILY_API_KEY` | backend | 선택 | 있으면 Planner가 실웹검색 사용 |
| `NEXT_PUBLIC_API_URL` | frontend | 필수(배포시) | 백엔드 공개 URL (빌드 시점에 고정됨) |

## 📡 API 명세

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/health` | 상태 확인 → `{ok, llm_mode}` (배포 헬스체크) |
| GET | `/api/agents` | 5개 역할 목록 (조직도 UI용) |
| POST | `/api/tasks` | 협업 실행. Body: `{goal, max_revisions=1}` → `TaskResult` |
| GET | `/api/tasks` | 저장된 작업 목록 |
| GET | `/api/tasks/{id}` | 특정 작업 조회 |

## 🚂 배포 (Railway)

모노레포 1개 → Railway 프로젝트 `ai-agent-company`에 서비스 3개:

| 서비스 | Root Directory | 빌드/시작 | 환경 변수 |
| --- | --- | --- | --- |
| backend | `backend` | Nixpacks, `uvicorn app.main:app --host 0.0.0.0 --port $PORT` | `OPENROUTER_API_KEY`(실모델), `DATABASE_URL`(Postgres 참조) |
| ai-agent-company (homepage) | `frontend` | `npm run build` → `npm start -- -p $PORT` | `NEXT_PUBLIC_API_URL`=(backend 도메인) |
| postgres | — | Railway Postgres 플러그인 | `DATABASE_URL` 자동 생성 |

배포 순서가 중요한 이유: `NEXT_PUBLIC_API_URL`은 Next.js 빌드 타임에 번들에 고정되므로
**backend 배포 → 도메인 발급 → frontend 변수 설정 → frontend 배포** 순으로 진행합니다.

## 🔮 향후 개선 방향

- [ ] SSE/WebSocket 스트리밍으로 에이전트 실행 과정 실시간 중계
- [ ] Claude / Gemini 모델 선택지 추가 (`llm.py` 확장)
- [ ] 역할·프롬프트를 UI에서 편집하는 에이전트 빌더
- [ ] 작업 이력 검색·비교 (Postgres `events` JSON 쿼리)
- [ ] LangSmith 트레이싱 연동으로 프롬프트 품질 관리
