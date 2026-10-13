/** Human-readable API errors; do not expose credentials or raw server response bodies. */
export function apiErrorMessage(status: number, detail: unknown, fallback: string): string {
  const detailText = typeof detail === 'string' ? detail.trim() : '';
  if (status === 401) return detailText || '서버 인증이 만료되었거나 유효하지 않습니다. 내 계정 > 연결 설정에서 다시 연결해주세요.';
  if (status === 403) return detailText || '접근 권한이 없습니다. 내 계정 > 연결 설정에서 서버 및 YouTube 연결을 확인해주세요.';
  if (status === 429) return '요청 한도에 도달했습니다. 잠시 후 다시 시도해주세요. (429)';
  if ([502, 503, 504].includes(status)) return '서버가 일시적으로 응답하지 않습니다. 무료 서버가 시작 중일 수 있으니 잠시 후 다시 시도해주세요. (' + status + ')';
  if (status >= 500) return '서버 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요. (' + status + ')';
  if (detailText) return detailText;
  if (status === 404) return '요청한 데이터를 찾지 못했습니다. (404)';
  if (status === 422 && Array.isArray(detail)) {
    const messages = detail
      .filter((item): item is { msg: string } => Boolean(item) && typeof item === 'object' && typeof item.msg === 'string')
      .map((item) => item.msg);
    if (messages.length) return '입력값을 확인해주세요: ' + messages.slice(0, 3).join(', ');
  }
  return fallback + ' (' + status + ')';
}

export function networkErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.name === 'AbortError') {
    return '서버 응답이 지연되어 요청 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.';
  }
  if (error instanceof TypeError) {
    return '서버에 연결하지 못했습니다. 네트워크 연결을 확인하고, 잠시 후 다시 시도해주세요.';
  }
  return error instanceof Error && error.message ? error.message : fallback;
}
