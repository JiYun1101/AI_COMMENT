const LEGACY_LABELS: Record<string, string> = {
  social: '사회이슈',
  social_issues: '사회이슈',
  vlog: '브이로그',
};

export function formatCategoryLabel(value: string | null | undefined): string {
  if (!value) return '기타';
  const key = value.trim().toLowerCase();
  return LEGACY_LABELS[key] ?? value;
}
