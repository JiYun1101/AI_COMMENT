## 프로젝트 로직 요약

### 프로젝트 개요

**AI Comment Recommender**는 크롤링된 게시글·댓글 데이터를 분석해, 같은 게시글 안에서 상대적으로 반응이 좋았던 댓글 패턴을 학습하고 새 게시글에 적합한 댓글 후보를 추천하는 FastAPI 기반 MVP입니다.

목표는 자극적인 댓글 생성이 아니라, **안전하고 자연스러운 댓글 후보를 점수화해 추천하는 것**입니다.

## YouTube 댓글 데이터 기반 모델 테스트 방법

이 프로젝트는 YouTube 댓글 데이터셋을 기반으로 댓글 후보의 예상 반응 점수를 계산합니다.
`social_issues_comments.csv`, `vlog_comments.csv`를 병합한 뒤 전처리, 피처 생성, 모델 학습, API 테스트 순서로 실행합니다.

### 1. 브랜치 확인

```bash
git branch --show-current
```

`develop` 브랜치에서 테스트합니다.

```bash
git switch develop
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. YouTube 댓글 데이터 병합

```bash
python scripts/prepare_combined_comments.py
```

정상 실행 시 `data/raw/comments.csv`가 생성됩니다.

결과 확인:

```bash
python -c "import pandas as pd; df=pd.read_csv('data/raw/comments.csv', encoding='utf-8-sig'); print(df.shape); print(df['category'].value_counts()); print(df['is_top_comment'].value_counts()); print(df['post_id'].nunique())"
```

기대 결과:

```text
- 댓글 수: 약 1.2만 건
- category: vlog / social_issues
- is_top_comment: 0과 1 모두 존재
- post_id: 수십 개 이상
```

### 4. 전처리 실행

```bash
python -m src.data.preprocess
```

결과 파일:

```text
data/processed/comments_processed.csv
```

### 5. 텍스트 피처 생성

```bash
python -m src.features.text_features
```

결과 파일:

```text
data/processed/comments_features.csv
```

피처 생성 확인:

```bash
python -c "import pandas as pd; df=pd.read_csv('data/processed/comments_features.csv', encoding='utf-8-sig'); print(df.shape); print(df[['post_id','comment_id','category','is_top_comment','post_comment_overlap_count','post_comment_jaccard','post_comment_coverage','post_comment_length_ratio']].head()); print(df['is_top_comment'].value_counts())"
```

확인할 것:

```text
- comments_features.csv가 1만 건 이상인지 확인
- is_top_comment 0/1 라벨이 모두 존재하는지 확인
- post_comment_overlap_count, post_comment_jaccard, post_comment_coverage, post_comment_length_ratio 컬럼이 생성되었는지 확인
```

### 6. 모델 학습

```bash
python -m src.model.train
```

정상 실행 시 `models/comment_ranker.joblib`이 생성됩니다.

학습 로그에서 확인할 것:

```text
- 전체 클래스 분포
- Train/Test 영상 수
- Train/Test 영상 중복 수: 0
- 언더샘플링 후 클래스 분포
- Accuracy / F1 Score
- Feature Importance
- 모델 저장 완료
```

### 7. 예측 함수 테스트

```bash
python -m src.model.predict
```

댓글 후보별 점수가 출력되면 정상입니다.

### 8. API 서버 실행

```bash
uvicorn src.api.main:app --reload
```

브라우저에서 Swagger 문서를 엽니다.

```text
http://127.0.0.1:8000/docs
```

### 9. `/score` API 테스트

Swagger의 `/score` 엔드포인트에서 아래 JSON을 입력합니다.

```json
{
  "post_text": "퇴근 후 혼자 밥 먹고 집 정리하는 직장인 브이로그",
  "comments": [
    "퇴근 후에도 자기 루틴을 지키는 게 진짜 쉽지 않은 것 같아요.",
    "AI를 잘 쓰려면 질문을 구조화하는 능력이 더 중요해질 것 같습니다.",
    "좋은 영상 감사합니다.",
    "ㅋㅋ 그냥 다 때려치우면 됨"
  ]
}
```

정상 응답 예시:

```json
{
  "post_text": "퇴근 후 혼자 밥 먹고 집 정리하는 직장인 브이로그",
  "results": [
    {
      "comment": "퇴근 후에도 자기 루틴을 지키는 게 진짜 쉽지 않은 것 같아요.",
      "score": 0
    }
  ]
}
```

점수는 학습 결과에 따라 달라질 수 있습니다.

### 10. 맥락 반영 테스트

같은 댓글 후보를 서로 다른 `post_text`에 넣어 점수가 달라지는지 확인합니다.

#### 브이로그 문맥

```json
{
  "post_text": "퇴근 후 혼자 밥 먹고 집 정리하는 직장인 브이로그",
  "comments": [
    "퇴근 후에도 자기 루틴을 지키는 게 진짜 쉽지 않은 것 같아요.",
    "AI를 잘 쓰려면 질문을 구조화하는 능력이 더 중요해질 것 같습니다."
  ]
}
```

#### AI/개발 문맥

```json
{
  "post_text": "AI 시대에 개발자는 어떤 역량을 키워야 할까?",
  "comments": [
    "퇴근 후에도 자기 루틴을 지키는 게 진짜 쉽지 않은 것 같아요.",
    "AI를 잘 쓰려면 질문을 구조화하는 능력이 더 중요해질 것 같습니다."
  ]
}
```

기대 결과:

```text
- 브이로그 문맥에서는 직장인/루틴 관련 댓글이 더 높게 평가됨
- AI/개발 문맥에서는 AI/질문 구조화 관련 댓글의 점수가 상대적으로 올라감
- post_text가 바뀌면 최종 score가 달라짐
```

### 11. `/recommend` API 테스트

Swagger의 `/recommend` 엔드포인트에서 아래 JSON을 입력합니다.

```json
{
  "post_text": "요즘 직장인 브이로그를 보면 현실적인 고민이 많이 보인다.",
  "top_k": 5
}
```

정상 응답 형태:

```json
{
  "post_text": "요즘 직장인 브이로그를 보면 현실적인 고민이 많이 보인다.",
  "recommendations": [
    {
      "rank": 1,
      "type": "empathy",
      "comment": "이 부분은 진짜 많은 사람들이 공감할 만한 내용이네요.",
      "predicted_score": 0
    }
  ]
}
```

### 12. 생성 파일 주의

아래 파일들은 실행 과정에서 생성되는 산출물이므로 일반적으로 Git 커밋 대상에서 제외합니다.

```text
data/raw/comments.csv
data/processed/comments_processed.csv
data/processed/comments_features.csv
data/processed/comments_scored_eval.csv
models/comment_ranker.joblib
```

---

### 전체 흐름

```text
CSV 데이터 입력
→ 전처리
→ 게시글별 좋아요 정규화
→ 댓글 피처 추출
→ 반응 예측 모델 학습
→ 댓글 후보 생성
→ 안전 필터링
→ 점수순 추천
```

---

### 주요 로직

| 로직             | 역할                                         | 선정 이유                                   |
| ---------------- | -------------------------------------------- | ------------------------------------------- |
| CSV 기반 입력    | 크롤링된 댓글 데이터 사용                    | MVP에서 가장 단순하고 재현 가능             |
| 좋아요 정규화    | 같은 게시글 내 댓글 반응을 상대 평가         | 게시글 인기 차이로 인한 좋아요 수 왜곡 방지 |
| 텍스트 피처 추출 | 길이, 질문, 웃음, 공감, 인사이트 표현 분석   | 댓글 반응에 영향을 주는 구조적 특징 반영    |
| 유형 분류        | 공감형, 인사이트형, 질문형, 캐주얼형 등 분류 | 추천 결과를 해석하기 쉽게 만들기 위함       |
| 반응 예측 모델   | 댓글 후보의 예상 반응 점수 계산              | 후보 댓글을 점수순으로 랭킹하기 위함        |
| 안전 필터        | 욕설, 비방, 혐오, 공격적 표현 제거           | 자극적 댓글 추천 방지                       |
| FastAPI API      | `/score`, `/recommend` 제공                  | 실제 서비스 형태로 테스트 가능              |

---

### 좋아요 정규화

댓글 좋아요 수는 게시글의 노출량과 인기 영향을 크게 받습니다.
따라서 절대 좋아요 수가 아니라 **같은 게시글 안에서 상위 반응 댓글인지**를 기준으로 라벨을 만듭니다.

```python
df["like_rank_pct"] = df.groupby("post_id")["like_count"].rank(pct=True)
df["label"] = (df["like_rank_pct"] >= 0.8).astype(int)
```

---

### 댓글 유형 분류

| 유형       | 설명                                      |
| ---------- | ----------------------------------------- |
| `empathy`  | 공감형 댓글                               |
| `insight`  | 게시글에 대한 해석이나 관점을 더하는 댓글 |
| `question` | 대화를 유도하는 질문형 댓글               |
| `casual`   | 자연스러운 구어체 댓글                    |
| `negative` | 부정적이거나 위험할 수 있는 표현          |
| `general`  | 특정 유형에 강하게 속하지 않는 일반 댓글  |

1차 MVP에서는 데이터가 적기 때문에 복잡한 분류 모델 대신 **키워드 기반 분류**를 사용했습니다.
이 방식은 구현이 빠르고, 결과를 해석하기 쉽다는 장점이 있습니다.

---

### 댓글 피처

모델은 댓글에서 다음과 같은 피처를 추출합니다.

```text
comment_length
word_count
question_count
exclamation_count
laugh_count
has_question
has_laugh
empathy_score
insight_score
negative_score
```

이 피처들은 댓글의 길이, 말투, 공감성, 인사이트 여부, 부정 표현 여부를 수치화하기 위한 값입니다.

---

### 추천 방식

댓글 추천은 다음 순서로 동작합니다.

```text
1. 게시글 입력
2. 안전한 템플릿 기반 댓글 후보 생성
3. 위험 표현 필터링
4. 후보별 반응 점수 예측
5. 점수 높은 순으로 top_k 댓글 반환
```

---

### API 구조

| API               | 역할                              |
| ----------------- | --------------------------------- |
| `GET /health`     | 서버 상태 확인                    |
| `POST /score`     | 사용자가 입력한 댓글 후보 점수화  |
| `POST /recommend` | 게시글에 맞는 댓글 후보 자동 추천 |

---

### 현재 MVP 범위

현재 버전은 모델 성능보다 **전체 추천 파이프라인이 끝까지 동작하는 것**에 초점을 둔 1차 MVP입니다.

구현된 기능은 다음과 같습니다.

```text
CSV 전처리
좋아요 정규화
댓글 피처 추출
반응 예측 모델 학습
댓글 후보 생성
안전 필터링
추천 랭킹
FastAPI Swagger 실행
```

---

### 향후 개선 방향

```text
데이터셋 확장
게시글-댓글 임베딩 유사도 추가
유형 분류 모델 고도화
안전 필터 개선
LightGBM/XGBoost 등 모델 비교
LLM 기반 댓글 후보 생성 도입
```

---

### 한 줄 요약

크롤링된 댓글 데이터를 기반으로 게시글 내 상대적 반응이 좋은 댓글 패턴을 학습하고, 새 게시글에 대해 안전한 댓글 후보를 점수화해 추천하는 FastAPI 기반 AI 댓글 추천 MVP입니다.

#현재 진행도
[완료] 프로젝트 폴더 구조
[완료] CSV 기반 전처리
[완료] 좋아요 정규화
[완료] 텍스트 피처 추출
[완료] 모델 학습 및 저장
[완료] 댓글 후보 점수화
[완료] 댓글 추천 랭킹
[완료] FastAPI 서버 구동
[완료] Swagger 문서 확인
[다음] /score, /recommend 실제 응답 테스트
[다음] 임베딩 피처 저장 확인
[다음] 데이터셋 확장
[다음] README 정리
