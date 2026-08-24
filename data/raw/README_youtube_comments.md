# YouTube 댓글 데이터셋 (social_issues / vlog)

'어떤 댓글이 반응이 좋은가'와 '어떤 댓글이 안전한가'를 학습시키기 위해
YouTube Data API v3로 수집한 카테고리별 댓글 데이터셋입니다.
기존 `comments.csv`(post_id, post_text, comment_id, comment_text,
like_count, created_at, platform)와 동일한 컬럼을 유지하고, 프로젝트
목적에 필요한 필드를 뒤에 추가했습니다.

## 파일

| 파일 | 카테고리 | 건수 | 고유 영상 수 |
|---|---|---|---|
| `social_issues_comments.csv` | 사회이슈 (시사/정치/사회 논쟁) | 6,585 | 50 |
| `vlog_comments.csv` | 브이로그 (일상/직장인/자취/여행) | 6,704 | 40 |

## 수집 방법

1. **영상 선정**: 카테고리별 4개 검색어 × 2가지 정렬(`order=viewCount`,
   `order=relevance`)로 검색하여 초대박 영상부터 니치한 영상까지 조회수
   규모를 섞어 후보를 구성했습니다.
2. **댓글 수집**: `commentThreads.list(order=relevance)`로 각 영상의
   최상위 댓글을 최대 300개까지 수집했습니다. 답글이 1~5개 달린 댓글에
   한해 `comments.list(parentId=...)`로 실제 답글도 함께 수집했습니다
   (API 쿼터 절약을 위해 영상당/카테고리당 상한을 두었습니다).
3. **노이즈 제거**: 이모티콘 전용 댓글, 구독/좋아요 유도·링크·연락처 등
   스팸 패턴, 한글 비중이 낮은(비한국어) 댓글을 정규식 기반으로 걸러냈습니다.
4. **라벨링**: 같은 영상(post) 내에서 `like_count` 기준 상위 15%에
   해당하는 댓글을 `is_top_comment=1`로 라벨링했습니다 (댓글 10개 미만인
   영상은 라벨링에서 제외하고 0으로 처리).

## 컬럼 설명

| 컬럼 | 설명 |
|---|---|
| `post_id` | 원본 영상 ID (기존 `comments.csv`의 `post_id`와 동일 의미) |
| `post_text` | 원본 영상 제목 |
| `comment_id` | 댓글 고유 ID |
| `comment_text` | 댓글 본문 |
| `like_count` | 좋아요 수 (반응도 핵심 지표) |
| `created_at` | 작성 시각 (ISO 8601) |
| `platform` | 항상 `youtube` |
| `category` | `social_issues` / `vlog` |
| `reply_count` | 답글 수 (최상위 댓글에 한해 집계, 답글 자체는 0) |
| `parent_id` | 부모 댓글 ID (최상위 댓글은 빈 값) |
| `video_view_count` | 원본 영상 조회수 (좋아요 정규화 기준) |
| `is_top_comment` | 영상 내 좋아요 상위 15% 여부 (1/0) — 안전/고품질 필터 학습용 라벨 |

## 재수집 방법

```bash
pip install -r requirements.txt
# .env.local에 YOUTUBE_API_KEY=... 설정 후
python scripts/collect_comments.py --category social_issues --target 5000
python scripts/collect_comments.py --category vlog --target 5000
```

## 주의사항

- 댓글 텍스트는 YouTube 공개 데이터이며, 작성자 식별 정보(채널명 등)는
  수집하지 않았습니다.
- 데이터 수집일: 2026-07-11 (YouTube 서비스 특성상 이후 좋아요 수 등은
  변동될 수 있습니다).
