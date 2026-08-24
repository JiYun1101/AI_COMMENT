import { ChevronDown, ListFilter } from 'lucide-react';

export interface FilterChip {
  k: string;
  v: string;
}

interface FilterFieldProps {
  label: string;
  value?: string;
  placeholder?: string;
}

function FilterField({ label, value, placeholder }: FilterFieldProps) {
  return (
    <div className="ff">
      <label className="ff-k">{label}</label>
      <div className="ff-input">
        <span>{value || <em>{placeholder}</em>}</span>
        <ChevronDown size={12} strokeWidth={2} />
      </div>
    </div>
  );
}

interface FilterBarProps {
  activeChips: FilterChip[];
  onRemoveChip: (chip: FilterChip) => void;
  onReset: () => void;
}

export function FilterBar({ activeChips, onRemoveChip, onReset }: FilterBarProps) {
  return (
    <div className="filterbar">
      <div className="ff-row">
        <FilterField label="브랜드" value="그린티코스메틱" />
        <FilterField label="키워드" value="여름 신제품" />
        <FilterField label="댓글 유형" placeholder="전체 유형" />
        <FilterField label="점수" placeholder="≥ 0.60" />
        <FilterField label="기간" value="7월 1 – 26일" />
        <div className="ff-actions">
          <button type="button" className="btn secondary sm" onClick={onReset}>
            초기화
          </button>
          <button type="button" className="btn primary sm">
            <ListFilter size={13} strokeWidth={2} />
            필터 적용
          </button>
        </div>
      </div>
      <div className="chip-row">
        {activeChips.map((c) => (
          <span key={c.k + c.v} className="chip active">
            <span className="chip-k">{c.k}:</span>&nbsp;{c.v}
            <span className="chip-x" onClick={() => onRemoveChip(c)}>
              ×
            </span>
          </span>
        ))}
        <span className="chip add">＋ 조건 추가</span>
      </div>
    </div>
  );
}
