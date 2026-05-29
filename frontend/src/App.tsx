import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { useState, useEffect, useRef } from 'react';
import InterviewView from './pages/InterviewView';
import ResearchView from './pages/ResearchView';
import EvaluationView from './pages/EvaluationView';
import { api } from './services/api';

type ConnectionStatus = 'connecting' | 'online' | 'offline';

function App() {
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const checkHealth = async () => {
    try {
      await api.health();
      setStatus('online');
    } catch {
      setStatus((prev) => (prev === 'online' ? 'offline' : prev));
    }
  };

  useEffect(() => {
    checkHealth();
    // Re-check every 60 seconds to detect backend going down or waking up
    intervalRef.current = setInterval(checkHealth, 60_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const statusLabel: Record<ConnectionStatus, string> = {
    connecting: 'Connecting to server…',
    online: 'System Online',
    offline: 'Server Unreachable',
  };

  const statusDotClass: Record<ConnectionStatus, string> = {
    connecting: 'connecting',
    online: 'active',
    offline: 'completed',
  };

  return (
    <BrowserRouter>
      <div className="app-layout">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-logo">
            <div className="logo-icon">🔬</div>
            <div>
              <h1>Research Lab</h1>
              <span className="subtitle">Autonomous AI Platform</span>
            </div>
          </div>
          <nav>
            <ul className="nav-links">
              <li>
                <NavLink
                  to="/interview"
                  className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                >
                  <span className="nav-icon">💬</span>
                  Interview
                </NavLink>
              </li>
              <li>
                <NavLink
                  to="/research"
                  className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                >
                  <span className="nav-icon">🔍</span>
                  Research
                </NavLink>
              </li>
              <li>
                <NavLink
                  to="/evaluation"
                  className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                >
                  <span className="nav-icon">📊</span>
                  Evaluation
                </NavLink>
              </li>
            </ul>
          </nav>
          <div style={{ marginTop: 'auto', paddingTop: '24px', borderTop: '1px solid var(--border)' }}>
            <div className="text-sm text-muted" style={{ padding: '0 12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className={`status-dot ${statusDotClass[status]}`}></span>
                {statusLabel[status]}
              </div>
              {status === 'connecting' && (
                <div style={{ fontSize: '11px', opacity: 0.6, marginTop: '4px', paddingLeft: '18px' }}>
                  Free-tier servers may take up to 60s to wake up.
                </div>
              )}
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/research" replace />} />
            <Route path="/interview" element={<InterviewView />} />
            <Route path="/research" element={<ResearchView />} />
            <Route path="/evaluation" element={<EvaluationView />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;

