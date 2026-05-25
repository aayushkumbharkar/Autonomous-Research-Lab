import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import InterviewView from './pages/InterviewView';
import ResearchView from './pages/ResearchView';
import EvaluationView from './pages/EvaluationView';

function App() {
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
                <span className="status-dot active"></span>
                System Online
              </div>
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
