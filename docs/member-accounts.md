# AI_COMMENT 회원 계정 (Supabase Auth)

## 실제 구현 기능
- 이메일 + 비밀번호 회원가입 / 로그인 / 로그아웃
- Supabase 이메일 인증 링크, 비밀번호 찾기, 새 비밀번호 저장
- 회원 닉네임(2~32자, 중복 가능) 저장 및 수정
- 세션 갱신/다른 탭의 로그인 상태 감지
- 회원별 비공개 추천 분석과 피드백 기록. Supabase RLS에서 \`auth.uid() = user_id\` 검증
- 로그인 회원의 \`/recommend\` 결과는 **기존 공용 SQLite 저장소에 넣지 않음**
- 비회원은 기존의 데모/개인 YouTube 게시 모드를 사용 가능 (회원가입 = YouTube OAuth 아님)

## 배포 환경의 필수 Supabase 설정

Supabase Dashboard → Authentication → URL Configuration

- **Site URL**: \`https://ai-comment-web.onrender.com\`
- **Allowed Redirect URLs**:
  - \`https://ai-comment-web.onrender.com/account/auth\`
  - \`https://ai-comment-web.onrender.com/account/reset\`
  - 개발용으로 \`http://localhost:5173/account/auth\` 및 \`http://localhost:5173/account/reset\`
- Authentication → Providers → Email: 이메일 로그인 활성화 및 신규 이메일 확인 설정
- 외부 사용자를 받으려면 운영용 SMTP 및 rate-limit/봇 방지를 별도 설정. 기본 Supabase 발송자는 소규모 테스트 목적이고 전송 제한이 있음

프론트엔드에서 필요한 공개 설정 (값은 브라우저에 공개되며 **service_role/secret 절대 금지**):

\`\`\`env
VITE_SUPABASE_URL=https://tyhpdlxbnsecjbyhdzuw.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<Supabase publishable key>
\`\`\`

같은 값이 기본값으로 코드에 포함되어 있어 현 Render 앱은 별도 변수 없이 UI 실행 가능. 다른 Supabase 프로젝트로 바꿀 때는 둘 다 변경해야 하며 \`ai_comment_profiles\`/\`ai_comment_saved_analyses\` 테이블을 동일하게 생성해야 함.

## 저장 모델
- 회원 인증: Supabase Auth (비밀번호는 프론트/Render DB에 보관하지 않음)
- 프로필: \`public.ai_comment_profiles\` (소유자만 접근)
- 개인 추천 기록: \`public.ai_comment_saved_analyses\` (RLS로 본인만 접근)
- 비회원/기존 기록: 종전 SQLite 보관함 (회원 가입 시 자동 이전 **안 함**)
- YouTube 연동 OAuth: 종전 서버 연결/YouTube 채널 설정을 사용. 다중 회원별 OAuth token 격리는 이번 작업 범위에 포함되지 않음.

## 검증 체크
1. 테스트 이메일 A 회원가입 후 인증 링크 클릭 → 로그인
2. 분석 1건 생성 → 로그아웃/로그인 후 같은 기록 표시
3. 사용자 B 회원가입 → A의 분석이 절대 표시되지 않는지 확인
4. 닉네임 변경, 로그아웃, 암호 재설정
5. 데모 모드와 개인 YouTube 게시 모드 분리 확인

## 알려진 제한
- 비밀번호 재설정 이메일/가입 확인 링크는 위 Auth Redirect 설정 없으면 정상 동작하지 않을 수 있음
- 이메일/계정 자체 삭제는 미구현 (향후 관리자 삭제 API 필요)
- 크로스 디바이스 회원 프로필/추천 분석은 동기화되지만 브라우저의 기존 API Key/YouTube OAuth/페르소나 설정은 계정별 클라우드 동기화 대상이 아님
- 기존 데모 분석 이력은 회원 전용 이력과 분리되어 있음
