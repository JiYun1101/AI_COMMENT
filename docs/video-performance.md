# 내 영상 성과 — YouTube Data API 연동

## 기능

- **소유 채널만 조회:** 서버에 저장된 Google OAuth 토큰으로 `channels.list(part=id,snippet,contentDetails&mine=true)` 조회. 영상마다 `snippet.channelId`가 연결된 채널과 일치하는지 검증
- **최근 업로드 영상 100개:** 채널 `contentDetails.relatedPlaylists.uploads`에서 `playlistItems.list`를 최대 2회 조회한 뒤, 최대 50개씩 묶어 `videos.list(part=snippet,statistics,status)` 조회. 일반 검색 엔드포인트 사용 안 함
- **오래된 영상:** 내 채널의 YouTube 영상 URL 또는 11자리 영상 ID를 직접 추가. 타 채널 소유 영상은 거부
- **지표:** YouTube가 반환하는 누적 viewCount/likeCount/commentCount. 미제공 지표는 0이 아닌 결측값
- **스냅샷:** SQLite 테이블 `owned_videos`, `owned_video_snapshots`, `owned_video_sync`에 YouTube 채널 ID별 저장. 5분 동기화 제한, 1시간 스냅샷 간격, 45일 보존
- **관측 변화:** 이전 측정 대비와 24시간(±6시간), 7일(±1일) 전 스냅샷 대비 변화. 해당 기준 측정이 없다면 `—`. **YouTube Analytics API의 정확한 일별 조회수와 다름**
- **백업:** 동일 브라우저의 `localStorage`에 채널 ID별 보조 백업 및 JSON 내보내기. 복구가 필요한 로컬 값은 현재 지표와 구분하여 표시

## 필요한 설정

1. 기존 `/account/connect` 페이지에서 서버 연결 및 **개인 계정** 모드 선택
2. YouTube OAuth Client ID/Secret 설정 → Google 계정/채널 연결
3. Google Cloud에서 **YouTube Data API v3** 활성화
4. Google OAuth의 Authorized redirect URI에는 현재 API 서버의 실제 `/youtube/oauth/callback` 주소를 등록
5. `/my-videos` 페이지에서 최초 가져오기(자동 시도) 또는 실제 반응 새로 확인

기존 댓글 게시 OAuth의 `youtube.force-ssl` 스코프로 계정의 YouTube Data API 조회를 수행하므로, 이번 기능만을 위해 더 넓은 Google 권한을 요구하지 않는다. 다른 계정의 영상을 읽거나 수정하는 API는 제공하지 않는다.

## API

- `GET /my-videos`: 인증된 채널의 캐시된 스냅샷/영상 목록
- `POST /my-videos/refresh`: 최근 100개 업로드 실측 값 가져오기. 5분 이내 재요청이면 `cached: true`를 반환
- `POST /my-videos/track`: `{"video_id":"<11-char-ID>"}` 개별 등록, 소유권 검증

모든 요청은 서버 `X-API-Key` 인증을 요구하고, 개인 계정 모드 및 YouTube OAuth 소유 채널 검증을 수행한다. 비밀키는 서버 로깅에 노출되지 않아야 하며, 브라우저가 기존 계정 설정에 저장한 자격증명은 `X-YouTube-OAuth-Client-ID/Secret`에만 전달한다.

YouTube Data API v3의 기본 비용: `channels.list`, `playlistItems.list`, `videos.list` 각 1 quota unit/호출(100개 업로드를 불러올 때 OAuth 소유권 확인 포함 대략 6 units, 쿼터 조건에 따라 달라질 수 있음). 호출 빈도는 서버 제한을 적용하며 Google 프로젝트의 실제 할당량을 반드시 확인한다.

## 영구 운영 전 반드시 확인할 사항

현재 실서비스 `ai-comment-api-lite`는 Render Free의 **비영구 SQLite 및 OAuth 토큰 파일**을 사용한다. 인스턴스 교체나 재배포 시 업로드/댓글 성과 기록이 사라질 수 있다. localStorage와 JSON 내보내기는 부가 백업이지 영구 DB가 아니다.

게시된 댓글의 기존 기록을 보존하기 위해 **운영 서버 무단 재배포 금지**. 기존 SQLite 및 OAuth 데이터를 먼저 안전하게 백업하고, 영구 DB/디스크를 연결·검증한 후 실제 OAuth 계정으로 E2E를 진행한다. 이 변경만으로 백그라운드 수집·일별 정확한 Analytics·기기 간 완전 동기화를 보장하지 않는다.

YouTube Analytics의 시청 시간, 평균 시청 지속률, 일별 조회수는 별도 API와 인증 범위가 필요하다. 이번 기능에서는 이를 추정해 표시하지 않는다.

## 테스트

`pytest -q` 및 `cd frontend && npm ci && npm test && npm run lint && npm run build`

테스트는 YouTube API 응답 mock, 소유 채널 교차 조회 차단, 다른 채널 URL 거부, 누락 지표, 데이터 채널별 분리, 24h/7d 스냅샷 차이, 5분 캐시, API 인증을 확인한다. 실계정 OAuth와 API 쿼터는 배포 환경에 필요한 별도 E2E 검증이다.
