export type ReadinessMode = 'url' | 'manual';

export interface RecommendationHealthLike {
  model: { ready: boolean };
  llm: { ready: boolean };
  youtube: { configured: boolean };
  storage: { ready: boolean };
}

export function getRecommendationReadinessMessage(
  health: RecommendationHealthLike | null,
  healthFailed: boolean,
  mode: ReadinessMode,
): string | null {
  if (healthFailed) return '추천 서비스 상태를 확인할 수 없습니다. 백엔드 연결 상태를 확인해주세요.';
  if (!health) return null;
  if (!health.storage.ready) return '저장소가 준비되지 않아 추천을 시작할 수 없습니다.';
  if (!health.model.ready) return '반응 예측 모델이 준비되지 않아 추천을 시작할 수 없습니다.';
  if (!health.llm.ready) return 'LLM 설정이 준비되지 않아 추천을 시작할 수 없습니다.';
  if (mode === 'url' && !health.youtube.configured) {
    return 'YouTube API가 설정되지 않았습니다. 직접 입력 모드는 사용할 수 있습니다.';
  }
  return null;
}
