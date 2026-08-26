# AI Comment

Act: Project
Cast: Graph/Workflow(Package)

<!-- AUTO-MANAGED: act-overview -->
## Act Overview

**Purpose:** 유튜브 영상 컨텍스트를 수집·분류한 뒤, 로컬 LLM으로 댓글 후보를 생성하고, 규칙 기반 안전 필터와 학습된 반응 예측 모델로 걸러 상위 후보를 추천한다. 사람이 승인한 댓글만 실제로 게시한다.
**Domain:** YouTube 댓글 추천 / 콘텐츠 생성 랭킹

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: casts-table -->
## Casts

| Cast Name | Purpose | Location |
|-----------|---------|----------|
| Comment Writer | 영상 컨텍스트 → 후보 생성 → 안전 필터 → 반응 점수 랭킹 → (사람 승인) → 게시 | `casts/comment_writer/` |

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: project-structure -->
## Project Structure

```
AI_COMMENT/
├── CLAUDE.md                    # Act 아키텍처 문서 (본 파일)
├── pyproject.toml               # uv 워크스페이스 / LangGraph 의존성
├── requirements.txt             # pip 경로 (CI가 사용)
├── langgraph.json               # LangGraph 그래프 엔트리포인트
├── .env.example                 # 환경변수 템플릿
├── casts/                       # LangGraph Cast 구현
│   ├── base_graph.py
│   ├── base_node.py
│   └── comment_writer/
│       ├── graph.py
│       ├── pyproject.toml
│       └── modules/
├── src/                         # 도메인 라이브러리 계층 (Cast가 감싸는 대상)
│   ├── youtube/                 # 영상 컨텍스트 수집
│   ├── recommender/             # 컨텍스트 빌드 · 안전 필터 · 랭킹
│   ├── features/ · model/       # 피처 스키마 · 반응 예측 모델
│   ├── llm/                     # LLM 클라이언트 (OpenAI / Ollama)
│   └── api/                     # FastAPI 서빙
└── tests/
```

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: development-commands -->
## Development Commands

### Dev Server

```bash
uv run langgraph dev
```

기존 FastAPI 서버는 그대로 유지된다.

```bash
uvicorn src.api.main:app --reload
```

### Sync Environment

```bash
uv sync --all-packages
uv sync --package comment-writer
```

### Create Cast

```bash
uv run act cast -c "<cast name>"
```

<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
## Notes

### 계층 규칙 (중요)

`src/` 는 LangGraph 를 모르는 **순수 도메인 라이브러리**로 유지한다.
의존 방향은 항상 한쪽이다.

```
casts/comment_writer/modules/tools.py  ──▶  src/*
src/*                                  ──▶  (casts 를 절대 import 하지 않음)
```

이 규칙 덕분에 기존 FastAPI 경로(`src/api/main.py`)와 LangGraph 경로가
같은 안전 필터·같은 랭커·같은 피처 스키마를 공유한다. 두 경로가 서로 다른
로직을 갖게 되면 예전 train/predict 피처 드리프트와 같은 종류의 버그가 재발한다.

### 파이프라인 (Comment Writer Cast)

```
영상 URL
  → context_node   : YouTube Data API 로 제목/설명/자막/통계 수집
  → build_node     : generation_context 구성 (post_text 확정)
  → generate_node  : 로컬 LLM 이 유형별 후보 생성
  → safety_node    : 규칙 기반 안전 필터 (LLM 아님, 결정적)
  → score_node     : 학습된 반응 예측 모델로 점수화
  → conditions     : 통과 후보 부족 시 피드백 붙여 generate_node 로 재생성
  → approval_gate  : HumanInTheLoopMiddleware — 사람 승인 없이는 게시 불가
  → post_node      : YouTube Data API 게시
```

### 설정 SSOT

- pytest 설정은 `pytest.ini` 한 곳만 사용한다. `pyproject.toml` 에는 두지 않는다.
- 피처 목록은 `src/features/feature_schema.py` 한 곳에서 파생된다.
- 런타임 의존성은 현재 `requirements.txt` 와 `pyproject.toml` 이중 관리다. uv 단일화는 후속 작업.

<!-- END MANUAL -->
