import { useState } from 'react';
import { api } from '../services/api';

function ScoreCard({ label, score, desc }: { label: string; score: number; desc?: string }) {
  const level = score >= 0.7 ? 'high' : score >= 0.4 ? 'medium' : 'low';
  return (
    <div className="score-card">
      <div className="score-label">{label}</div>
      <div className={`score-value ${level}`}>{(score * 100).toFixed(0)}%</div>
      <div className="score-bar">
        <div className={`score-bar-fill ${level}`} style={{ width: `${score * 100}%` }} />
      </div>
      {desc && <div className="text-sm text-muted mt-8">{desc}</div>}
    </div>
  );
}

function TrustPanel({ confidence, claims }: { confidence: any; claims: any[] }) {
  if (!confidence) return null;
  const level = confidence.risk_level || 'medium';
  const confPct = ((confidence.confidence || 0) * 100).toFixed(0);

  const supported = claims.filter((c: any) => c.status === 'supported').length;
  const partial = claims.filter((c: any) => c.status === 'partially_supported').length;
  const unsupported = claims.filter((c: any) => c.status === 'unsupported').length;

  return (
    <div className="trust-panel">
      <div className="trust-header">
        🛡️ Why Should I Trust This?
      </div>

      <div className="flex items-center justify-between mb-8">
        <span className="text-sm">Confidence</span>
        <div className="flex items-center gap-8">
          <span style={{ fontWeight: 700, fontSize: '18px' }}>{confPct}%</span>
          <span className={`risk-badge ${level}`}>
            {level === 'low' ? '✅ Low Risk' : level === 'medium' ? '⚠️ Medium Risk' : '🚨 High Risk'}
          </span>
        </div>
      </div>

      <div className="confidence-meter">
        <div
          className="confidence-fill"
          style={{
            width: `${confPct}%`,
            background:
              level === 'low'
                ? 'var(--success)'
                : level === 'medium'
                ? 'var(--warning)'
                : 'var(--error)',
          }}
        />
      </div>

      {confidence.explanation && (
        <div className="text-sm text-muted mt-8">{confidence.explanation}</div>
      )}

      {confidence.disagreement_score != null && (
        <div className="text-sm mt-8" style={{ color: 'var(--info)' }}>
          Dual-run disagreement: {(confidence.disagreement_score * 100).toFixed(0)}%
        </div>
      )}

      {claims.length > 0 && (
        <div className="mt-16">
          <div className="text-sm" style={{ fontWeight: 600, marginBottom: '8px' }}>
            Claim Verification ({supported + partial}/{claims.length} grounded)
          </div>
          <div className="claim-list">
            {claims.map((c: any, i: number) => (
              <div key={i} className="claim-item">
                <span className="claim-status">
                  {c.status === 'supported' ? '✅' : c.status === 'partially_supported' ? '🟡' : '❌'}
                </span>
                <span>{c.claim.slice(0, 120)}{c.claim.length > 120 ? '...' : ''}</span>
              </div>
            ))}
          </div>
          {unsupported > 0 && (
            <div className="mt-8 text-sm" style={{ color: 'var(--error)' }}>
              ⚠️ {unsupported} unsupported claim{unsupported > 1 ? 's' : ''} detected
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ResearchView() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showIngest, setShowIngest] = useState(false);
  const [ingestText, setIngestText] = useState('');
  const [ingestName, setIngestName] = useState('');
  const [ingesting, setIngesting] = useState(false);

  const submitQuery = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await api.submitQuery(query);
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const ingest = async () => {
    if (!ingestText.trim() || !ingestName.trim()) return;
    setIngesting(true);
    try {
      await api.ingestText(ingestText, ingestName);
      setIngestText('');
      setIngestName('');
      setShowIngest(false);
      alert('Transcript ingested successfully!');
    } catch (e: any) {
      alert(e.message);
    } finally {
      setIngesting(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div>
            <h2>🔍 Research Lab</h2>
            <p>Ask questions and receive grounded, citation-backed answers</p>
          </div>
          <button className="btn btn-secondary" onClick={() => setShowIngest(!showIngest)}>
            📄 {showIngest ? 'Hide' : 'Ingest Data'}
          </button>
        </div>
      </div>

      <div className="page-body">
        {/* Ingest Panel */}
        {showIngest && (
          <div className="card mb-16" style={{ animation: 'fadeInUp 0.3s ease' }}>
            <div className="card-title" style={{ marginBottom: '12px' }}>📄 Ingest Transcript</div>
            <input
              className="input mb-8"
              placeholder="Filename (e.g., interview_01.txt)"
              value={ingestName}
              onChange={(e) => setIngestName(e.target.value)}
            />
            <textarea
              className="textarea"
              placeholder="Paste transcript text here...&#10;&#10;Speaker: Hello, I'm here to discuss...&#10;[00:01] Welcome to the interview..."
              value={ingestText}
              onChange={(e) => setIngestText(e.target.value)}
              style={{ minHeight: '150px' }}
            />
            <button className="btn btn-primary mt-8" onClick={ingest} disabled={ingesting}>
              {ingesting ? <span className="loading-spinner" /> : 'Upload & Process'}
            </button>
          </div>
        )}

        {/* Query Input */}
        <div className="card mb-16">
          <div className="flex gap-12">
            <input
              className="input"
              placeholder="Ask a research question..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submitQuery()}
              style={{ flex: 1 }}
            />
            <button className="btn btn-primary" onClick={submitQuery} disabled={loading}>
              {loading ? <span className="loading-spinner" /> : '🔍 Research'}
            </button>
          </div>
        </div>

        {error && (
          <div className="card mb-16" style={{ borderColor: 'rgba(248,113,113,0.3)', background: 'var(--error-bg)' }}>
            <span style={{ color: 'var(--error)' }}>❌ {error}</span>
          </div>
        )}

        {loading && (
          <div className="empty-state">
            <div className="loading-spinner" style={{ width: '40px', height: '40px' }} />
            <p className="text-muted mt-16">
              Searching → Generating → Verifying Claims → Evaluating...
            </p>
          </div>
        )}

        {result && (
          <div className="grid-2" style={{ alignItems: 'start' }}>
            {/* Left: Answer + Citations */}
            <div className="flex flex-col gap-16">
              {/* Answer */}
              <div className="card">
                <div className="card-header">
                  <span className="card-title">Answer</span>
                  {result.eval_scores && (
                    <span
                      className={`risk-badge ${
                        result.eval_scores.composite >= 0.7
                          ? 'low'
                          : result.eval_scores.composite >= 0.4
                          ? 'medium'
                          : 'high'
                      }`}
                    >
                      Score: {(result.eval_scores.composite * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7, fontSize: '14px' }}>
                  {result.answer_text}
                </div>
                {result.reasoning_trace && (
                  <details className="mt-16">
                    <summary className="text-sm text-muted" style={{ cursor: 'pointer' }}>
                      🧠 Reasoning Trace
                    </summary>
                    <div className="text-sm font-mono mt-8" style={{ color: 'var(--text-muted)', padding: '8px', background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)' }}>
                      {result.reasoning_trace}
                    </div>
                  </details>
                )}
              </div>

              {/* Citations */}
              {result.citations && result.citations.length > 0 && (
                <div className="card">
                  <div className="card-title mb-8">📎 Citations ({result.citations.length})</div>
                  <div className="flex flex-col gap-8">
                    {result.citations.map((cit: any) => (
                      <div key={cit.index} className="chunk-card">
                        <div className="chunk-score">[{cit.index}] {(cit.relevance_score * 100).toFixed(0)}%</div>
                        <div>{cit.content.slice(0, 300)}{cit.content.length > 300 ? '...' : ''}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Eval Scores */}
              {result.eval_scores && (
                <div className="card">
                  <div className="card-title mb-16">📊 Evaluation Scores</div>
                  <div className="score-grid">
                    <ScoreCard label="Faithfulness" score={result.eval_scores.composite || 0} />
                    <ScoreCard label="Citation Coverage" score={result.eval_scores.citation_coverage || 0} />
                    <ScoreCard label="Retrieval Overlap" score={result.eval_scores.retrieval_overlap || 0} />
                    <ScoreCard label="Claim Support" score={result.eval_scores.claim_support_ratio || 0} />
                  </div>
                </div>
              )}
            </div>

            {/* Right: Trust Panel */}
            <div className="flex flex-col gap-16">
              <TrustPanel
                confidence={result.confidence}
                claims={result.claim_verifications || []}
              />

              {/* Attempt Info */}
              {result.attempt_number > 1 && (
                <div className="card" style={{ borderColor: 'rgba(99,102,241,0.3)' }}>
                  <div className="card-title mb-8">🔄 Auto-Improved</div>
                  <div className="text-sm text-muted">
                    This answer was improved through {result.attempt_number - 1} retry attempt(s)
                    via the feedback loop.
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {!result && !loading && (
          <div className="empty-state">
            <div className="empty-icon">🔬</div>
            <h3>Ready for Research</h3>
            <p className="text-muted mt-8">
              Ingest some data first, then ask a research question.
              <br />
              The system will retrieve context, generate a grounded answer,
              <br />
              verify claims, compute confidence, and evaluate quality.
            </p>
          </div>
        )}
      </div>
    </>
  );
}
