import { Sparkles, ChevronRight } from 'lucide-react';
import type { Category } from '../../types/comment';

export interface ExampleVideo {
  title: string;
  channel: string;
  tag: string;
  category: Category;
  c1: string;
  c2: string;
}

const EXAMPLES: ExampleVideo[] = [
  { title: 'AI 시대에 개발자는 어떻게 살아남아야 할까?', channel: '테크살롱', tag: '사회이슈', category: 'social', c1: '#1e40af', c2: '#7c3aed' },
  { title: '마케터의 하루 — 여름 캠페인 준비 브이로그', channel: '리테일노트', tag: '브이로그', category: 'vlog', c1: '#0f766e', c2: '#14b8a6' },
  { title: '올해 여름 신제품 언박싱 & 실사용 후기', channel: '그린티코스메틱', tag: '브이로그', category: 'vlog', c1: '#be185d', c2: '#f472b6' },
];

interface EmptyExamplesProps {
  onPick: (example: ExampleVideo) => void;
}

export function EmptyExamples({ onPick }: EmptyExamplesProps) {
  return (
    <div className="examples">
      <div className="examples-h">
        <Sparkles size={14} strokeWidth={1.75} />
        <h3>이런 영상으로 시작해보세요</h3>
        <span className="sub">클릭하면 예시 제목이 직접 입력에 채워집니다</span>
      </div>
      <div className="example-list">
        {EXAMPLES.map((example) => (
          <button
            key={example.title}
            type="button"
            className="example-item"
            onClick={() => onPick(example)}
            style={{ '--c1': example.c1, '--c2': example.c2 } as React.CSSProperties}
          >
            <div className="example-thumb" />
            <div className="example-body">
              <div className="example-title">{example.title}</div>
              <div className="example-meta">{example.channel}</div>
            </div>
            <span className="example-tag">{example.tag}</span>
            <span className="example-arrow">
              <ChevronRight size={14} strokeWidth={2} />
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
