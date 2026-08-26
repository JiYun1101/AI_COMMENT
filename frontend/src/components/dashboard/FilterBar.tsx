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

const COMMON_CATEGORIES = [
  'Film & Animation',
  'Autos & Vehicles',
  'Music',
  'Pets & Animals',
  'Sports',
  'Travel & Events',
  'Gaming',
  'People & Blogs',
  'Comedy',
  'Entertainment',
  'News & Politics',
  'Howto & Style',
  'Education',
  'Science & Technology',
  'Nonprofits & Activism',
];

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
          <input
            id="filter-category"
            className="filter-native"
            list="youtube-category-options"
            value={value.category}
            onChange={(event) => update('category', event.target.value)}
            placeholder="공식/파생 카테고리"
          />
          <datalist id="youtube-category-options">
            {COMMON_CATEGORIES.map((category) => <option key={category} value={category} />)}
            <option value="social" />
            <option value="vlog" />
          </datalist>
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
