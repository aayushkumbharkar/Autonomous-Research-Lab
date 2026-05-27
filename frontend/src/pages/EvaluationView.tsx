import { useState, useEffect } from 'react';
import { api } from '../services/api';

function ScoreCard({ label, score }: { label: string; score: number }) {
  const level = score >= 0.7 ? 'high' : score >= 0.4 ? 'medium' : 'low';
  return (
    <div className="score-card">
      <div className="score-label">{label}</div>
      <div className={`score-value ${level}`}>{(score * 100).toFixed(0)}%</div>
      <div className="score-bar">
        <div className={`score-bar-fill ${level}`} style={{ width: `${score * 100}%` }} />
      </div>
    </div>
  );
}

export default function EvaluationView() {
  const [queries, setQueries] = useState<any[]>([]);
  const [selectedQuery, setSelectedQuery] = useState<string | null>(null);
  const [comparison, setComparison] = useState<any>(null);
  const [evalRuns, setEvalRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [coverage, setCoverage] = useState<any>(null);

  useEffect(() => {
    api.listQueries().then(setQueries).catch(console.error);
    api.listEvalRuns().then(setEvalRuns).catch(console.error);
    api.coverage().then(setCoverage).catch(() => {});
  }, []);

  const loadComparison = async (queryId: string) => {
    setSelectedQuery(queryId);
    setLoading(true);
    try {
      const comp = await api.getRetryComparison(queryId);
      setComparison(comp);
    } catch (e: any) {
      console.error(e);
      setComparison(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <h2>📊 Evaluation Dashboard</h2>
        <p>Review scores, failure explanations, retry comparisons, and system health</p>
      </div>

      <div className="page-body">
        {/* Data Coverage */}
        {coverage && (
          <div className="card mb-16">
            <div className="card-title mb-16">📦 Data Coverage</div>
            <div className="grid-3">
              <div className="score-card">
                <div className="score-label">Transcripts</div>
                <div className="score-value" style={{ color: 'var(--accent-primary)' }}>
                  {coverage.total_transcripts}
                </div>
              </div>
              <div className="score-card">
                <div className="score-label">Indexed Chunks</div>
                <div className="score-value" style={{ color: 'var(--accent-primary)' }}>
                  {coverage.total_chunks}
                </div>
              </div>
              <div className="score-card">
                <div className="score-label">Assessment</div>
                <div
                  className={`score-value ${
                    coverage.coverage_assessment === 'good'
                      ? 'high'
                      : coverage.coverage_assessment === 'moderate'
                      ? 'medium'
                      : 'low'
                  }`}
                  style={{ fontSize: '20px' }}
                >
                  {coverage.coverage_assessment?.toUpperCase()}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Eval Runs Summary */}
        {evalRuns.length > 0 && (
          <div className="card mb-16">
            <div className="card-title mb-16">🏅 Recent Evaluations</div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={{ textAlign: 'left', padding: '8px 12px', color: 'var(--text-secondary)' }}>
                      ID
                    </th>
                    <th style={{ textAlign: 'center', padding: '8px 12px', color: 'var(--text-secondary)' }}>
                      Composite
                    </th>
                    <th style={{ textAlign: 'center', padding: '8px 12px', color: 'var(--text-secondary)' }}>
                      Citation Cov.
                    </th>
                    <th style={{ textAlign: 'center', padding: '8px 12px', color: 'var(--text-secondary)' }}>
                      Ret. Overlap
                    </th>
                    <th style={{ textAlign: 'center', padding: '8px 12px', color: 'var(--text-secondary)' }}>
                      Claim Support
                    </th>
                    <th style={{ textAlign: 'right', padding: '8px 12px', color: 'var(--text-secondary)' }}>
                      Date
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {evalRuns.slice(0, 10).map((run: any) => {
                    const level =
                      run.composite_score >= 0.7 ? 'high' : run.composite_score >= 0.4 ? 'medium' : 'low';
                    return (
                      <tr key={run.id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '10px 12px', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                          {run.id.slice(0, 8)}...
                        </td>
                        <td style={{ textAlign: 'center', padding: '10px 12px' }}>
                          <span className={`risk-badge ${level}`}>
                            {(run.composite_score * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td style={{ textAlign: 'center', padding: '10px 12px' }}>
                          {(run.citation_coverage * 100).toFixed(0)}%
                        </td>
                        <td style={{ textAlign: 'center', padding: '10px 12px' }}>
                          {(run.retrieval_overlap * 100).toFixed(0)}%
                        </td>
                        <td style={{ textAlign: 'center', padding: '10px 12px' }}>
                          {(run.claim_support_ratio * 100).toFixed(0)}%
                        </td>
                        <td
                          style={{
                            textAlign: 'right',
                            padding: '10px 12px',
                            color: 'var(--text-muted)',
                            fontSize: '12px',
                          }}
                        >
                          {new Date(run.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Failure Replay */}
        <div className="card mb-16">
          <div className="card-title mb-16">🔁 Failure Replay — Retry Comparisons</div>

          {queries.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">📝</div>
              <p className="text-muted">No queries yet. Run a research query first.</p>
            </div>
          ) : (
            <div className="flex gap-16" style={{ flexWrap: 'wrap', marginBottom: '16px' }}>
              {queries.map((q: any) => (
                <button
                  key={q.id}
                  className={`btn ${selectedQuery === q.id ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                  onClick={() => loadComparison(q.id)}
                >
                  {q.query_text.slice(0, 50)}{q.query_text.length > 50 ? '...' : ''} ({q.answer_count} attempts)
                </button>
              ))}
            </div>
          )}

          {loading && (
            <div className="flex items-center gap-12 mt-16">
              <span className="loading-spinner" />
              <span className="text-muted">Loading comparison...</span>
            </div>
          )}

          {comparison && (
            <div style={{ animation: 'fadeInUp 0.3s ease' }}>
              <div className="flex items-center justify-between mb-16">
                <div className="text-sm text-muted">Query: "{comparison.query_text}"</div>
                <div>
                  {comparison.total_improvement > 0 ? (
                    <span className="risk-badge low">
                      📈 +{(comparison.total_improvement * 100).toFixed(0)}% improvement
                    </span>
                  ) : comparison.total_improvement === 0 ? (
                    <span className="risk-badge medium">No change</span>
                  ) : (
                    <span className="risk-badge high">
                      📉 {(comparison.total_improvement * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              </div>

              <div className="flex flex-col gap-16">
                {comparison.attempts.map((attempt: any) => {
                  const isBest = attempt.attempt_number === comparison.best_attempt;
                  return (
                    <div
                      key={attempt.answer_id}
                      className="card"
                      style={{
                        borderColor: isBest ? 'rgba(52,211,153,0.4)' : 'var(--border)',
                        position: 'relative',
                      }}
                    >
                      {isBest && (
                        <div
                          style={{
                            position: 'absolute',
                            top: '-10px',
                            right: '12px',
                            background: 'var(--success)',
                            color: '#000',
                            padding: '2px 10px',
                            borderRadius: '100px',
                            fontSize: '11px',
                            fontWeight: 700,
                          }}
                        >
                          ✨ Best Attempt
                        </div>
                      )}

                      <div className="flex items-center justify-between mb-8">
                        <div className="card-title">
                          Attempt #{attempt.attempt_number}
                          <span className="text-sm text-muted" style={{ fontWeight: 400, marginLeft: '8px' }}>
                            ({attempt.modification_type})
                          </span>
                        </div>
                        {attempt.scores.composite != null && (
                          <span
                            className={`risk-badge ${
                              attempt.scores.composite >= 0.7
                                ? 'low'
                                : attempt.scores.composite >= 0.4
                                ? 'medium'
                                : 'high'
                            }`}
                          >
                            {(attempt.scores.composite * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>

                      <div className="text-sm" style={{ whiteSpace: 'pre-wrap', maxHeight: '120px', overflow: 'auto' }}>
                        {attempt.answer_text.slice(0, 500)}
                        {attempt.answer_text.length > 500 ? '...' : ''}
                      </div>

                      {attempt.improvement !== 0 && (
                        <div
                          className="text-sm mt-8"
                          style={{
                            color:
                              attempt.improvement > 0 ? 'var(--success)' : 'var(--error)',
                          }}
                        >
                          {attempt.improvement > 0 ? '📈' : '📉'} {(attempt.improvement * 100).toFixed(1)}%
                          from previous
                        </div>
                      )}

                      {Object.keys(attempt.scores).length > 0 && (
                        <div className="score-grid mt-16" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))' }}>
                          {Object.entries(attempt.scores)
                            .filter(([k]) => k !== 'composite')
                            .slice(0, 4)
                            .map(([key, val]: [string, any]) => (
                              <ScoreCard key={key} label={key.replace(/_/g, ' ')} score={val} />
                            ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
