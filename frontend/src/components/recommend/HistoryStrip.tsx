import { ChevronRight, MessageSquare } from 'lucide-react';

interface HistoryItem {
  id: string;
  title: string;
  duration: string;
  count: number;
  time: string;
  tag: string;
  c1: string;
  c2: string;
}

const HISTORY: HistoryItem[] = [
  {
    id: 'h1',
    title: '결국 문제 정의 능력이 자산이 되는 시대 — 시니어 개발자의 관점',
    duration: '18:04',
    count: 8,
    time: '2시간 전',
    tag: '사회이슈',
    c1: '#1e40af',
    c2: '#7c3aed',
  },
  {
    id: 'h2',
    title: '스몰 브랜드 마케터가 매일 하는 3가지 — 브이로그 EP.12',
    duration: '09:47',
    count: 5,
    time: '어제',
    tag: '브이로그',
    c1: '#0f766e',
    c2: '#14b8a6',
  },
  {
    id: 'h3',
    title: '올해 여름 신제품 언박싱 & 실사용 후기 (한 달 사용)',
    duration: '11:23',
    count: 10,
    time: '3일 전',
    tag: '브이로그',
    c1: '#be185d',
    c2: '#f472b6',
  },
];

// Real API: GET /me/recent-analyses?limit=3 (not yet exposed by the backend — mocked for now)
export function HistoryStrip() {
  return (
    <section>
      <div className="section-h">
        <div>
          <h2>최근 분석한 영상</h2>
          <div className="sub" style={{ marginTop: 3 }}>
            최근 3건 · 최대 30일 보관
          </div>
        </div>
        <a href="#recent">
          전체 보기
          <ChevronRight size={12} strokeWidth={2} />
        </a>
      </div>
      <div className="history">
        {HISTORY.map((item) => (
          <button
            key={item.id}
            type="button"
            className="hist-card"
            style={{ '--c1': item.c1, '--c2': item.c2 } as React.CSSProperties}
          >
            <div className="hist-thumb">
              <span className="badge">{item.tag}</span>
              <span className="dur">{item.duration}</span>
            </div>
            <div className="hist-body">
              <div className="hist-title">{item.title}</div>
              <div className="hist-meta">
                <span className="count">
                  <MessageSquare size={11} strokeWidth={2} />
                  추천 {item.count}개
                </span>
                <span className="time">{item.time}</span>
              </div>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
