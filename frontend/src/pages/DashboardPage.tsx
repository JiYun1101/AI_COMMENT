import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import { Header } from '../components/layout/Header';
import { KpiStrip } from '../components/dashboard/KpiStrip';
import { FilterBar, type FilterChip } from '../components/dashboard/FilterBar';
import { DataTable, type CommentRow } from '../components/dashboard/DataTable';
import { GeneratePanel } from '../components/dashboard/GeneratePanel';

const SEED_ROWS: CommentRow[] = [
  { id: 'c_88291', text: '결국 문제를 정의하는 능력이 중요해질 것 같아요. 툴 자체보다 문제 감각이 자산이 되는 시대네요.', type: 'insight', brand: '그린티코스메틱', score: 0.847, date: '2026-07-26' },
  { id: 'c_88290', text: '와 이거 진짜 공감돼요. 저도 처음엔 비슷하게 접근했는데 결과가 훨씬 좋았어요.', type: 'empathy', brand: '그린티코스메틱', score: 0.812, date: '2026-07-26' },
  { id: 'c_88289', text: '혹시 여기서 참고하신 논문이나 자료 링크 공유 가능할까요? 팀에서도 스터디하고 싶어요.', type: 'question', brand: '스마트홈랩', score: 0.774, date: '2026-07-25' },
  { id: 'c_88288', text: '영상 편집 진짜 깔끔해요 ㅋㅋㅋ 다음 편도 기대 중', type: 'casual', brand: '스마트홈랩', score: 0.731, date: '2026-07-25' },
  { id: 'c_88287', text: '이런 프로젝트는 포트폴리오로도 좋아 보이네요. 신입 관점에서 배울 점이 많습니다.', type: 'insight', brand: '커리어콘', score: 0.702, date: '2026-07-25' },
  { id: 'c_88286', text: '좋은 영상 잘 봤습니다. 항상 감사드립니다.', type: 'general', brand: '커리어콘', score: 0.641, date: '2026-07-24' },
  { id: 'c_88285', text: '진짜 정보 밀도 미쳤네요. 두 번 봤어요.', type: 'empathy', brand: '그린티코스메틱', score: 0.628, date: '2026-07-24' },
  { id: 'c_88284', text: '초반 인트로 부분 다시 만들면 훨씬 좋을 것 같은데, 편집 시간이 문제겠죠?', type: 'question', brand: '스마트홈랩', score: 0.594, date: '2026-07-24' },
];

const INITIAL_CHIPS: FilterChip[] = [
  { k: '브랜드', v: '그린티코스메틱' },
  { k: '키워드', v: '여름 신제품' },
  { k: '유형', v: '인사이트' },
  { k: '기간', v: '7월 1–26일' },
];

// NOTE: rows/KPIs are seed data — the backend has no /comments listing or
// /kpis endpoint yet. Wire this page up once those routes exist.
export function DashboardPage() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [chips, setChips] = useState<FilterChip[]>(INITIAL_CHIPS);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const rows = SEED_ROWS;

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    setSelected((prev) => (prev.size === rows.length ? new Set() : new Set(rows.map((r) => r.id))));
  };

  const removeChip = (chip: FilterChip) => setChips((prev) => prev.filter((c) => c !== chip));

  const handleNav = (key: SidebarKey) => {
    if (key === 'comments') navigate('/');
    // other nav targets have no route yet
  };

  return (
    <div className="app">
      <Sidebar current="dashboard" onNav={handleNav} />
      <div className="main">
        <Header
          title="댓글"
          subtitle="유튜브 영상에서 생성 · 수집된 댓글을 브랜드/키워드로 필터링하고 CSV로 내보냅니다."
          onGenerate={() => setDrawerOpen(true)}
        />
        <div className="content">
          <KpiStrip />
          <FilterBar activeChips={chips} onRemoveChip={removeChip} onReset={() => setChips([])} />
          <DataTable rows={rows} selected={selected} onToggle={toggle} onToggleAll={toggleAll} />
        </div>
      </div>
      <GeneratePanel open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </div>
  );
}
