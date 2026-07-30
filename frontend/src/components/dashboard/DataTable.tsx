import { Check, Minus, Download, ListFilter, MoreVertical } from 'lucide-react';
import { TypeTag } from '../TypeTag';

export interface CommentRow {
  id: string;
  text: string;
  type: string;
  brand: string;
  score: number;
  date: string;
}

function ScoreBar({ value }: { value: number }) {
  return (
    <div className="score-cell">
      <span className="score-num">{value.toFixed(3)}</span>
      <div className="score-bar">
        <div className="score-fill" style={{ width: `${value * 100}%` }} />
      </div>
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
    <span className={`cb${on ? ' on' : ''}${indeterminate ? ' indet' : ''}`} onClick={onChange} role="checkbox" aria-checked={on}>
      {on && !indeterminate && <Check size={11} strokeWidth={2.5} color="#fff" />}
      {indeterminate && <Minus size={11} strokeWidth={2.5} color="#fff" />}
    </span>
  );
}

interface DataTableProps {
  rows: CommentRow[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: () => void;
}

export function DataTable({ rows, selected, onToggle, onToggleAll }: DataTableProps) {
  const allOn = selected.size === rows.length && rows.length > 0;
  const someOn = selected.size > 0 && !allOn;

  return (
    <div className="table-wrap">
      <div className="table-toolbar">
        <div className="tt-left">
          {selected.size > 0 ? (
            <>
              <b>{selected.size}건</b> 선택됨
              <button type="button" className="btn secondary sm">
                <Download size={13} strokeWidth={2} />
                선택 항목 내보내기
              </button>
              <button type="button" className="btn ghost sm danger">
                삭제
              </button>
            </>
          ) : (
            <>
              <span className="tt-count">
                총 <b>3,214</b>건
              </span>
              <button type="button" className="btn secondary sm">
                <ListFilter size={13} strokeWidth={2} />
                정렬: Score ↓
              </button>
            </>
          )}
        </div>
        <div className="tt-right">
          <button type="button" className="btn success sm">
            <Download size={13} strokeWidth={2} />
            CSV 다운로드
          </button>
        </div>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th style={{ width: 34 }}>
              <Checkbox on={allOn} indeterminate={someOn} onChange={onToggleAll} />
            </th>
            <th style={{ width: 110 }}>ID</th>
            <th>댓글 내용</th>
            <th style={{ width: 110 }}>유형</th>
            <th style={{ width: 140 }}>브랜드</th>
            <th style={{ width: 130 }}>Score</th>
            <th style={{ width: 130 }}>생성일</th>
            <th style={{ width: 40 }} />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className={selected.has(r.id) ? 'sel' : ''}>
              <td>
                <Checkbox on={selected.has(r.id)} onChange={() => onToggle(r.id)} />
              </td>
              <td className="mono muted">{r.id}</td>
              <td className="content">{r.text}</td>
              <td>
                <TypeTag type={r.type} />
              </td>
              <td className="muted">{r.brand}</td>
              <td>
                <ScoreBar value={r.score} />
              </td>
              <td className="mono muted small">{r.date}</td>
              <td>
                <button type="button" className="icon-btn tiny" title="더보기">
                  <MoreVertical size={14} strokeWidth={2} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="pagination">
        <div className="pg">
          <button type="button" className="pg-b ghost">
            ‹
          </button>
          <button type="button" className="pg-b">
            1
          </button>
          <button type="button" className="pg-b active">
            2
          </button>
          <button type="button" className="pg-b">
            3
          </button>
          <button type="button" className="pg-b">
            4
          </button>
          <span className="pg-sep">…</span>
          <button type="button" className="pg-b">
            128
          </button>
          <button type="button" className="pg-b ghost">
            ›
          </button>
        </div>
        <span className="pg-info">2 / 128 · 총 3,214건 · 25개씩 보기</span>
      </div>
    </div>
  );
}
