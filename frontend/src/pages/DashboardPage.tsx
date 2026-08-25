import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getDashboardSummary, listComments } from '../api/client';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import { Header } from '../components/layout/Header';
import { KpiStrip } from '../components/dashboard/KpiStrip';
import { FilterBar, type DashboardFilters } from '../components/dashboard/FilterBar';
import { DataTable } from '../components/dashboard/DataTable';
import type { DashboardComment, DashboardSummary } from '../types/comment';

const EMPTY_FILTERS: DashboardFilters = { query: '', type: '', category: '', minScore: '' };
const PAGE_SIZE = 25;

function csvEscape(value: string | number | null): string {
  const text = value == null ? '' : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [rows, setRows] = useState<DashboardComment[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [draftFilters, setDraftFilters] = useState<DashboardFilters>(EMPTY_FILTERS);
  const [filters, setFilters] = useState<DashboardFilters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);

  const loadSummary = useCallback(() => {
    setSummaryLoading(true);
    getDashboardSummary()
      .then(setSummary)
      .catch((err) => setError(err instanceof Error ? err.message : '대시보드 요약을 불러오지 못했습니다.'))
      .finally(() => setSummaryLoading(false));
  }, []);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const parsedScore = filters.minScore.trim() ? Number(filters.minScore) : undefined;
    listComments({
      query: filters.query.trim() || undefined,
      type: filters.type || undefined,
      category: filters.category || undefined,
      minScore: parsedScore !== undefined && Number.isFinite(parsedScore) ? parsedScore : undefined,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    })
      .then((response) => {
        if (cancelled) return;
        setRows(response.items);
        setTotal(response.total);
        setSelected(new Set());
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : '댓글 목록을 불러오지 못했습니다.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters, page]);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    setSelected((prev) => {
      const currentPageIds = rows.map((row) => row.id);
      const allSelected = currentPageIds.length > 0 && currentPageIds.every((id) => prev.has(id));
      const next = new Set(prev);
      currentPageIds.forEach((id) => (allSelected ? next.delete(id) : next.add(id)));
      return next;
    });
  };

  const applyFilters = () => {
    setPage(1);
    setFilters({ ...draftFilters });
  };

  const resetFilters = () => {
    setDraftFilters(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setPage(1);
  };

  const exportCsv = () => {
    const exportRows = selected.size > 0 ? rows.filter((row) => selected.has(row.id)) : rows;
    if (exportRows.length === 0) return;
    const header = ['id', 'comment', 'type', 'source', 'channel', 'category', 'predicted_score', 'feedback', 'created_at'];
    const lines = [header.map(csvEscape).join(',')];
    exportRows.forEach((row) => {
      lines.push(
        [
          row.id,
          row.comment,
          row.type,
          row.video_title || '직접 입력',
          row.channel,
          row.category,
          row.predicted_score,
          row.feedback,
          row.created_at,
        ].map(csvEscape).join(','),
      );
    });
    const blob = new Blob([`\uFEFF${lines.join('\n')}`], { type: 'text/csv;charset=utf-8' });
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = href;
    anchor.download = `ai-comment-results-${new Date().toISOString().slice(0, 10)}.csv`;
    anchor.click();
    URL.revokeObjectURL(href);
  };

  const handleNav = (key: SidebarKey) => {
    if (key === 'comments') navigate('/');
    if (key === 'dashboard') navigate('/dashboard');
  };

  return (
    <div className="app">
      <Sidebar current="dashboard" onNav={handleNav} />
      <div className="main">
        <Header
          title="대시보드"
          subtitle="실제로 생성·저장된 추천 댓글을 검색하고 점수·유형·카테고리로 필터링합니다."
          onGenerate={() => navigate('/')}
        />
        <div className="content">
          <KpiStrip summary={summary} loading={summaryLoading} />
          <FilterBar value={draftFilters} onChange={setDraftFilters} onApply={applyFilters} onReset={resetFilters} />
          {error && <div className="dashboard-state error">{error}</div>}
          <DataTable
            rows={rows}
            total={total}
            selected={selected}
            onToggle={toggle}
            onToggleAll={toggleAll}
            onExport={exportCsv}
            page={page}
            pageSize={PAGE_SIZE}
            onPage={setPage}
            loading={loading}
          />
        </div>
      </div>
    </div>
  );
}
