import { ListFilter, RotateCcw } from 'lucide-react';

export interface DashboardFilters {
  query: string;
  type: string;
  category: string;
  minScore: string;
}

interface FilterBarProps {
  value: DashboardFilters;
  onChange: (next: DashboardFilters) => void;
  onApply: () => void;
  onReset: () => void;
}

export function FilterBar({ value, onChange, onApply, onReset }: FilterBarProps) {
  const update = (key: keyof DashboardFilters, nextValue: string) => {
    onChange({ ...value, [key]: nextValue });
  };

  return (
    <form
      className="filterbar real-filterbar"
      onSubmit={(event) => {
        event.preventDefault();
        onApply();
      }}
    >
      <div className="ff-row">
        <div className="ff grow">
          <label className="ff-k" htmlFor="filter-query">검색</label>
          <input
            id="filter-query"
            className="filter-native"
            value={value.query}
            onChange={(event) => update('query', event.target.value)}
            placeholder="댓글 · 영상 제목 검색"
          />
        </div>
        <div className="ff">
          <label className="ff-k" htmlFor="filter-type">댓글 유형</label>
          <select id="filter-type" className="filter-native" value={value.type} onChange={(event) => update('type', event.target.value)}>
            <option value="">전체 유형</option>
            <option value="insight">인사이트</option>
            <option value="empathy">공감형</option>
            <option value="question">질문형</option>
            <option value="casual">캐주얼</option>
            <option value="general">일반</option>
          </select>
        </div>
        <div className="ff">
          <label className="ff-k" htmlFor="filter-category">카테고리</label>
          <select id="filter-category" className="filter-native" value={value.category} onChange={(event) => update('category', event.target.value)}>
            <option value="">전체</option>
            <option value="social">사회이슈</option>
            <option value="vlog">브이로그</option>
          </select>
        </div>
        <div className="ff score-filter">
          <label className="ff-k" htmlFor="filter-score">최소 점수</label>
          <input
            id="filter-score"
            className="filter-native"
            type="number"
            min="0"
            max="100"
            step="1"
            value={value.minScore}
            onChange={(event) => update('minScore', event.target.value)}
            placeholder="0–100"
          />
        </div>
        <div className="ff-actions">
          <button type="button" className="btn secondary sm" onClick={onReset}>
            <RotateCcw size={13} /> 초기화
          </button>
          <button type="submit" className="btn primary sm">
            <ListFilter size={13} strokeWidth={2} /> 필터 적용
          </button>
        </div>
      </div>
    </form>
  );
}
