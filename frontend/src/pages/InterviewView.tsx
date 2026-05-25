import { useState, useRef, useEffect } from 'react';
import { api } from '../services/api';

interface Message {
  id: string;
  role: 'moderator' | 'participant';
  content: string;
  created_at: string;
}

interface Session {
  id: string;
  topic: string;
  status: string;
  messages: Message[];
  summary?: string;
}

export default function InterviewView() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const [topic, setTopic] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [sendingMsg, setSendingMsg] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.listSessions().then(setSessions).catch(console.error);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeSession?.messages]);

  const startSession = async () => {
    if (!topic.trim()) return;
    setLoading(true);
    try {
      const session = await api.startSession(topic);
      setActiveSession(session);
      setTopic('');
      setSessions((prev) => [{ ...session, message_count: 1 }, ...prev]);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!message.trim() || !activeSession) return;
    setSendingMsg(true);

    // Optimistically add participant message
    const tempMsg: Message = {
      id: 'temp-' + Date.now(),
      role: 'participant',
      content: message,
      created_at: new Date().toISOString(),
    };
    setActiveSession((prev) =>
      prev ? { ...prev, messages: [...prev.messages, tempMsg] } : prev
    );
    setMessage('');

    try {
      const response = await api.sendMessage(activeSession.id, message);
      setActiveSession((prev) => {
        if (!prev) return prev;
        const msgs = prev.messages.filter((m) => m.id !== tempMsg.id);
        return {
          ...prev,
          messages: [...msgs, { ...tempMsg, id: tempMsg.id.replace('temp-', '') }, response.message],
        };
      });
    } catch (e: any) {
      alert(e.message);
    } finally {
      setSendingMsg(false);
    }
  };

  const endSession = async () => {
    if (!activeSession) return;
    setLoading(true);
    try {
      const result = await api.endSession(activeSession.id);
      setActiveSession(result);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setLoading(false);
    }
  };

  const loadSession = async (id: string) => {
    try {
      const session = await api.getSession(id);
      setActiveSession(session);
    } catch (e: any) {
      alert(e.message);
    }
  };

  return (
    <>
      <div className="page-header">
        <h2>💬 Interview Lab</h2>
        <p>Conduct adaptive AI-moderated interviews and explore insights</p>
      </div>
      <div className="page-body" style={{ display: 'flex', gap: '24px', height: 'calc(100vh - 100px)' }}>
        {/* Session List */}
        <div style={{ width: '280px', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="card" style={{ padding: '16px' }}>
            <div className="card-title" style={{ marginBottom: '12px' }}>New Interview</div>
            <input
              className="input"
              placeholder="Interview topic..."
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && startSession()}
            />
            <button
              className="btn btn-primary w-full mt-8"
              onClick={startSession}
              disabled={loading || !topic.trim()}
            >
              {loading ? <span className="loading-spinner" /> : '🎙️ Start Session'}
            </button>
          </div>

          <div className="card" style={{ flex: 1, overflow: 'auto', padding: '12px' }}>
            <div className="card-title" style={{ marginBottom: '12px', padding: '0 4px' }}>Past Sessions</div>
            {sessions.length === 0 ? (
              <div className="text-sm text-muted" style={{ textAlign: 'center', padding: '20px 0' }}>
                No sessions yet
              </div>
            ) : (
              <div className="flex flex-col gap-8">
                {sessions.map((s) => (
                  <div
                    key={s.id}
                    className="nav-link"
                    onClick={() => loadSession(s.id)}
                    style={{
                      ...(activeSession?.id === s.id
                        ? { background: 'rgba(99,102,241,0.15)', color: 'var(--accent-primary)' }
                        : {}),
                    }}
                  >
                    <span className={`status-dot ${s.status}`}></span>
                    <div>
                      <div style={{ fontSize: '13px', fontWeight: 600 }}>{s.topic.slice(0, 40)}</div>
                      <div className="text-sm text-muted">{s.message_count || 0} messages</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Chat Area */}
        <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {!activeSession ? (
            <div className="empty-state" style={{ flex: 1 }}>
              <div className="empty-icon">🎙️</div>
              <h3>Start an Interview</h3>
              <p className="text-muted mt-8">
                Enter a topic and start an AI-moderated interview session
              </p>
            </div>
          ) : (
            <div className="chat-container" style={{ height: '100%' }}>
              {/* Header */}
              <div className="flex items-center justify-between" style={{ padding: '0 0 16px', borderBottom: '1px solid var(--border)' }}>
                <div>
                  <div className="card-title">{activeSession.topic}</div>
                  <div className="text-sm text-muted flex items-center gap-8">
                    <span className={`status-dot ${activeSession.status}`}></span>
                    {activeSession.status}
                  </div>
                </div>
                {activeSession.status === 'active' && (
                  <button className="btn btn-secondary btn-sm" onClick={endSession}>
                    End & Summarize
                  </button>
                )}
              </div>

              {/* Messages */}
              <div className="chat-messages" style={{ flex: 1, overflow: 'auto' }}>
                {activeSession.messages.map((msg) => (
                  <div key={msg.id} className={`message ${msg.role}`}>
                    <div className="message-avatar">
                      {msg.role === 'moderator' ? '🤖' : '👤'}
                    </div>
                    <div className="message-bubble">{msg.content}</div>
                  </div>
                ))}
                {sendingMsg && (
                  <div className="message moderator">
                    <div className="message-avatar">🤖</div>
                    <div className="message-bubble">
                      <span className="loading-dots">Thinking</span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Summary */}
              {activeSession.summary && (
                <div className="card mt-16" style={{ background: 'var(--bg-tertiary)' }}>
                  <div className="card-title" style={{ marginBottom: '8px' }}>📝 Session Summary</div>
                  <div className="text-sm" style={{ whiteSpace: 'pre-wrap' }}>
                    {activeSession.summary}
                  </div>
                </div>
              )}

              {/* Input */}
              {activeSession.status === 'active' && (
                <div className="chat-input-area">
                  <input
                    className="input"
                    placeholder="Type your response..."
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                    disabled={sendingMsg}
                  />
                  <button
                    className="btn btn-primary"
                    onClick={sendMessage}
                    disabled={sendingMsg || !message.trim()}
                  >
                    Send
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
