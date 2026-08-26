# Comment Writer Cast

유튜브 영상 컨텍스트를 수집해 댓글 후보를 만들고, 안전 필터와 반응 예측 모델로
걸러 상위 후보를 추천하는 LangGraph Cast입니다.

## 목표 파이프라인

```text
영상 URL
  → ContextNode    : YouTube Data API 로 제목/설명/자막/통계 수집  [구현됨]
  → GenerateNode   : 로컬 LLM 이 유형별 후보 생성                  [예정]
  → SafetyNode     : 규칙 기반 안전 필터 (LLM 아님, 결정적)        [예정]
  → ScoreNode      : 학습된 반응 예측 모델로 점수화                [예정]
  → conditions     : 후보 부족 시 피드백 붙여 재생성               [예정]
  → 승인 게이트    : HumanInTheLoopMiddleware                      [예정]
  → PostNode       : YouTube Data API 게시                          [예정]
```

## 구조

```text
comment_writer/
├── graph.py           # StateGraph 조립 (필수)
├── modules/
│   ├── state.py       # InputState / OutputState / State 3분리 (필수)
│   ├── nodes.py       # BaseNode 상속 노드 (필수)
│   ├── tools.py       # src/ 도메인 계층을 감싸는 얇은 어댑터
│   ├── models.py      # LLM 팩토리 (ollama / openai)
│   ├── prompts.py     # src/llm/prompting.py 재노출 + 재생성 피드백 조립
│   ├── conditions.py  # 조건부 라우팅 (예정)
│   ├── middlewares.py # HITL 등 미들웨어 (예정)
│   ├── agents.py      # create_agent 구성 (예정)
│   └── utils.py
└── pyproject.toml
```

## 계층 규칙

```text
casts/comment_writer/modules/*  ──▶  src/*
src/*                           ──▶  (casts 를 절대 import 하지 않음)
```

`src/` 는 LangGraph 를 모르는 순수 도메인 라이브러리로 유지합니다. 덕분에
기존 FastAPI 경로와 이 Cast 가 **같은 안전 필터 · 같은 랭커 · 같은 프롬프트**를
공유합니다.

## 사용 방법

```python
from casts.comment_writer.graph import comment_writer_graph

graph = comment_writer_graph()
result = graph.invoke({"video_url": "https://www.youtube.com/watch?v=..."})
```

## 의존성 추가

```bash
uv add <패키지명> --package comment-writer
```
