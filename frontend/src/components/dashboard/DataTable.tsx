import { Check, Download, Minus } from 'lucide-react';
import { TypeTag } from '../TypeTag';
import { formatCategoryLabel } from '../../utils/category';
import type { DashboardComment } from '../../types/comment';

function ScoreBar({ value }: { value: number }) {
  return (
    <div className="score-cell">
      <span className="score-num">{value.toFixed(1)}%</span>
      <div className="score-bar"><div className="score-fill" style={{ width: `${Math.min(100, Math.max(0, value))}%` }} /></div>
    </div>
  );
}

interface CheckboxProps {
  on: boolean;
  indeterminate?: boolean;
  onChange: () => void;
}

function Checkbox({ on, indeterminate, onChange }: CheckboxProps) {
  return (
    <button
      type="button"
      className={`cb${on ? ' on' : ''}${indeterminate ? ' indet' : ''}`}
      onClick={onChange}
      role="checkbox"
      aria-checked={indeterminate ? 'mixed' : on}
    >
      {on && !indeterminate && <Check size={11} strokeWidth={2.5} color="#fff" />}
      {indeterminate && <Minus size={11} strokeWidth={2.5} color="#fff" />}
    </button>
  );
}

interface DataTableProps {
  rows: DashboardComment[];
  total: number;
  selected: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: () => void;
  onExport: () => void;
  page: number;
  pageSize: number;
  onPage: (page: number) => void;
  loading?: boolean;
}

export function DataTable({
  rows,
  total,
  selected,
  onToggle,
  onToggleAll,
  onExport,
  page,
  pageSize,
  onPage,
  loading,
}: DataTableProps) {
  const allOn = rows.length > 0 && rows.every((row) => selected.has(row.id));
  const selectedOnPage = rows.filter((row) => selected.has(row.id)).length;
  const someOn = selectedOnPage > 0 && !allOn;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="table-wrap">
      <div className="table-toolbar">
        <div className="tt-left">
          <span className="tt-count">총 <b>{total}</b>건</span>
          {selected.size > 0 && <span><b>{selected.size}건</b> 선택됨</span>}
        </div>
        <div className="tt-right">
          <button type="button" className="btn success sm" onClick={onExport} disabled={rows.length === 0}>
            <Download size={13} strokeWidth={2} />
            {selected.size > 0 ? '선택 항목 CSV' : '현재 목록 CSV'}
          </button>
        </div>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th style={{ width: 34 }}><Checkbox on={allOn} indeterminate={someOn} onChange={onToggleAll} /></th>
            <th style={{ width: 120 }}>ID</th>
            <th>댓글 내용</th>
            <th style={{ width: 105 }}>유형</th>
            <th style={{ width: 210 }}>영상 / 입력</th>
            <th style={{ width: 150 }}>카테고리</th>
            <th style={{ width: 130 }}>Score</th>
            <th style={{ width: 110 }}>피드백</th>
            <th style={{ width: 120 }}>생성일</th>
          </tr>
        </thead>
        <tbody>
          {loading && (
            <tr><td colSpan={9} className="table-empty">댓글 목록을 불러오는 중…</td></tr>
          )}
          {!loading && rows.length === 0 && (
            <tr><td colSpan={9} className="table-empty">조건에 맞는 실제 추천 댓글이 없습니다.</td></tr>
          )}
          {!loading && rows.map((row) => (
            <tr key={row.id} className={selected.has(row.id) ? 'sel' : ''}>
              <td><Checkbox on={selected.has(row.id)} onChange={() => onToggle(row.id)} /></td>
              <td className="mono muted">{row.id}</td>
              <td className="content">{row.comment}</td>
              <td><TypeTag type={row.type} /></td>
              <td>
                <div className="table-source">{row.video_title || '직접 입력'}</div>
                {row.channel && <div className="table-source-sub">{row.channel}</div>}
              </td>
              <td className="muted">{formatCategoryLabel(row.category)}</td>
              <td><ScoreBar value={row.predicted_score} /></td>
              <td className="muted">
                {row.feedback === 'useful' ? '도움됨' : row.feedback === 'not_useful' ? '아쉬움' : '—'}
              </td>
              <td className="mono muted small">{new Date(row.created_at).toLocaleDateString('ko-KR')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="pagination real-pagination">
        <button type="button" className="btn secondary sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>이전</button>
        <span className="pg-info">{page} / {totalPages} · 페이지당 {pageSize}건</span>
        <button type="button" className="btn secondary sm" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>다음</button>
      </div>
    </div>
  );
}
