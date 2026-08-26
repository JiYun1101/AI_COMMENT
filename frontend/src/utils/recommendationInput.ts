export type RecommendationInputMode = 'url' | 'manual';

interface RecommendationInputReadyParams {
  mode: RecommendationInputMode;
  urlValid: boolean;
  manualLength: number;
  previewReady: boolean;
  previewLoading: boolean;
}

export function isRecommendationInputReady({
  mode,
  urlValid,
  manualLength,
  previewReady,
  previewLoading,
}: RecommendationInputReadyParams): boolean {
  if (mode === 'manual') return manualLength >= 5;
  return urlValid && previewReady && !previewLoading;
}
