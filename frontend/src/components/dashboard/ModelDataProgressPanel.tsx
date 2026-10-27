import { ArrowRight, Database, Layers3, LoaderCircle, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { getModelDataProgress, getStoredApiAccessToken } from '../../api/client';
import { Link } from 'react-router-dom';
import type { ModelDataProgress } from '../../types/comment';

const number = (value: number) => value.toLocaleString('ko-KR');

export function ModelDataProgressPanel() {
  const [data, setData] = useState<ModelDataProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    if (!getStoredApiAccessToken()) {
      setData(null);
      setError('분석 데이터 조회에는 별도의 서버 연결이 필요합니다. 이메일 회원 로그인과 서버 연결은 서로 다릅니다.');
      setLoading(false);
      return;
    }
    try {
      setData(await getModelDataProgress());
    } catch (cause) {
      setData(null);
      setError(cause instanceof Error ? cause.message : '모델 데이터 조회 실패');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const chart = useMemo(() => {
    if (!data?.daily.length) return '';
    const maximum = Math.max(1, ...data.daily.map((point) => point.cumulative_analyses));
    const denominator = Math.max(1, data.daily.length - 1);
    return data.daily.map((point, index) => {
      const x = 18 + 664 * index / denominator;
      const y = 136 - 108 * point.cumulative_analyses / maximum;
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
  }, [data]);

  return (
    <section className="model-panel" aria-label="LLM 앞단 데이터 모델">
      <div className="model-panel-header">
        <div>
          <span className="model-eyebrow"><Database size={15} /> BEFORE THE LLM · DATA FOUNDATION</span>
          <h2>AI가 참고하는 데이터는 어떻게 쌓일까?</h2>
          <p>영상 특징을 코드로 분류하고 기존 댓글에서 관련 사례를 찾아 LLM에 전달합니다. 아래 수치는 서버 공용 분석 기록 기준이며, 회원별 Supabase 비공개 분석은 포함하지 않습니다.</p>
        </div>
        <button type="button" className="btn secondary sm" disabled={loading} onClick={() => void load()}>
          {loading ? <LoaderCircle size={14} className="spin" /> : <RefreshCw size={14} />} 새로고침
        </button>
      </div>

      <div className="model-flow" aria-label="데이터 처리 흐름">
        <div className="model-step"><small>01 · 입력</small><strong>영상·자막</strong><span>제목, 설명, 영상 지표</span></div>
        <ArrowRight size={17} aria-hidden="true" />
        <div className="model-step"><small>02 · 코드 분석</small><strong>영상 맥락 분류</strong><span>주제, 형식, 신선도</span></div>
        <ArrowRight size={17} aria-hidden="true" />
        <div className="model-step emphasized"><small>03 · 데이터 참조</small><strong>과거 댓글 검색</strong><span>관련 사례·말투 통계</span></div>
        <ArrowRight size={17} aria-hidden="true" />
        <div className="model-step model-step-llm"><small>04 · 생성 AI</small><strong>LLM 후보 생성</strong><span>앞단의 데이터 참조</span></div>
      </div>
      <p className="model-flow-caption">이후 단계: 안전성 검사 → 별도의 학습된 반응 예측 Ranker → 최종 추천. 앞의 맥락 분류와 댓글 검색은 별도로 재학습되는 신경망이 아닙니다.</p>

      {error && <div className="inline-status" role="status">{error} <Link to="/account/connect">서버 연결 설정 확인</Link></div>}
      {loading && !data && <p className="eng-note" role="status">저장된 자료를 확인 중입니다…</p>}

      {data && (
        <>
          <div className="model-metrics">
            <div><span>검색 가능한 과거 댓글</span><strong>{number(data.reference.usable_comments)}<small>건</small></strong><em>고정 참고 데이터 · {data.reference.sources.length}개 소스</em></div>
            <div><span>누적 맥락 분석</span><strong>{number(data.observations.stored_contexts)}<small>회</small></strong><em>실제 생성 요청 기록</em></div>
            <div><span>서로 다른 분석 영상</span><strong>{number(data.observations.unique_videos)}<small>개</small></strong><em>YouTube 영상 ID 기준</em></div>
            <div><span>축적된 사용자 평가</span><strong>{number(data.observations.feedback)}<small>건</small></strong><em>향후 개선에 활용 가능</em></div>
          </div>

          <div className="model-lower">
            <div className="model-chart-panel">
              <div className="model-subhead"><strong><Layers3 size={16} /> 분석 기록이 쌓이는 흐름</strong><small>지난 14일 · 누적 분석 횟수</small></div>
              <svg viewBox="0 0 700 155" role="img" aria-label="지난 14일 누적 분석 기록 추세" className="model-progress-chart" preserveAspectRatio="none">
                <line x1="18" y1="136" x2="682" y2="136" stroke="currentColor" opacity="0.15" />
                {chart && <polyline points={chart} fill="none" stroke="#6366f1" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />}
              </svg>
              <div className="model-chart-footer">
                <span>{data.daily[0]?.date.slice(5) ?? ''}</span>
                <span>{number(data.daily.reduce((total, item) => total + item.new_analyses, 0))}건 신규 분석</span>
                <span>{data.daily[data.daily.length - 1]?.date.slice(5) ?? ''}</span>
              </div>
            </div>
            <div className="model-sources">
              <div className="model-subhead"><strong>기존 댓글 참고 데이터</strong><small>LLM 이전 검색 자료</small></div>
              {data.reference.sources.map((source, index) => (
                <div className="model-source" key={source.name}>
                  <div><span>{source.name.replaceAll('_', ' ')}</span><strong>{number(source.count)}건</strong></div>
                  <div className="model-source-track"><span className={index % 2 === 0 ? 'source-a' : 'source-b'}
                    style={{ width: (100 * source.count / Math.max(1, data.reference.usable_comments)).toFixed(1) + '%' }} /></div>
                </div>
              ))}
              <div className="model-source-foot">
                <span>실제 기존 댓글을 매칭한 분석</span>
                <strong>{number(data.observations.historical_matched_analyses)}건</strong>
              </div>
              <small className="eng-note">한 분석에서 평균 {data.observations.average_matches == null ? '—' : number(data.observations.average_matches)}개 사례 참조 (매칭 분석만 집계)</small>
            </div>
          </div>
          <p className="model-safety-note"><strong>데이터 누적 ≠ 자동 학습.</strong> 새 분석과 피드백은 저장되지만, 현재 반응 예측 모델의 가중치가 자동으로 바뀌지는 않습니다. {data.note}</p>
        </>
      )}
    </section>
  );
}
