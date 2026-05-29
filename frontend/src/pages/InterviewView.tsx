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

  // STT / TTS state
  const [isListening, setIsListening] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const [speakingMsgId, setSpeakingMsgId] = useState<string | null>(null);
  const recognitionRef = useRef<any>(null);
  const initialMessageRef = useRef<string>('');

  useEffect(() => {
    api.listSessions().then(setSessions).catch(console.error);

    // Initialize SpeechRecognition
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      const rec = new SpeechRecognition();
      rec.continuous = false;
      rec.interimResults = false;
      rec.lang = 'en-US';

      rec.onstart = () => {
        setIsListening(true);
      };
      rec.onend = () => {
        setIsListening(false);
      };
      rec.onerror = (e: any) => {
        console.error("Speech recognition error:", e);
        setIsListening(false);
      };
      rec.onresult = (event: any) => {
        let sessionTranscript = '';
        for (let i = 0; i < event.results.length; i++) {
          sessionTranscript += event.results[i][0].transcript;
        }
        const initial = initialMessageRef.current || '';
        setMessage(initial ? `${initial.trim()} ${sessionTranscript.trim()}` : sessionTranscript.trim());
      };
      recognitionRef.current = rec;
    }

    return () => {
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeSession?.messages]);

  const speakText = (text: string, msgId: string) => {
    if (!('speechSynthesis' in window)) {
      alert("Text-to-speech is not supported in this browser.");
      return;
    }

    if (speakingMsgId === msgId) {
      window.speechSynthesis.cancel();
      setSpeakingMsgId(null);
      return;
    }

    window.speechSynthesis.cancel();
    if (!text) return;

    // Remove any formatting or metadata lines from the speech utterance
    const cleanText = text.replace(/TOPICS_(COVERED|REMAINING):.*/gi, '').trim();

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.onend = () => {
      setSpeakingMsgId(null);
    };
    utterance.onerror = () => {
      setSpeakingMsgId(null);
    };

    setSpeakingMsgId(msgId);
    window.speechSynthesis.speak(utterance);
  };

  const toggleListening = () => {
    if (!recognitionRef.current) {
      alert("Speech recognition is not supported in this browser. Please use Google Chrome, Microsoft Edge, or Apple Safari.");
      return;
    }
    if (isListening) {
      recognitionRef.current.stop();
    } else {
      try {
        initialMessageRef.current = message;
        recognitionRef.current.start();
      } catch (e) {
        console.error(e);
      }
    }
  };

  const startSession = async () => {
    if (!topic.trim()) return;
    setLoading(true);
    try {
      const session = await api.startSession(topic);
      setActiveSession(session);
      setTopic('');
      setSessions((prev) => [{ ...session, message_count: 1 }, ...prev]);

      if (autoSpeak && session.messages && session.messages.length > 0) {
        const opening = session.messages[0];
        speakText(opening.content, opening.id);
      }
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

      if (autoSpeak) {
        speakText(response.message.content, response.message.id);
      }
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
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
      setSpeakingMsgId(null);
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
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
      setSpeakingMsgId(null);
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
                      position: 'relative',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      paddingRight: '32px',
                      ...(activeSession?.id === s.id
                        ? { background: 'rgba(99,102,241,0.15)', color: 'var(--accent-primary)' }
                        : {}),
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', overflow: 'hidden' }}>
                      <span className={`status-dot ${s.status}`}></span>
                      <div style={{ overflow: 'hidden' }}>
                        <div style={{ fontSize: '13px', fontWeight: 600, whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>{s.topic}</div>
                        <div className="text-sm text-muted">{s.message_count || 0} messages</div>
                      </div>
                    </div>
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        if (confirm(`Are you sure you want to delete this session?`)) {
                          try {
                            await api.deleteSession(s.id);
                            setSessions((prev) => prev.filter((session) => session.id !== s.id));
                            if (activeSession?.id === s.id) {
                              setActiveSession(null);
                            }
                          } catch (err: any) {
                            alert(err.message);
                          }
                        }
                      }}
                      style={{
                        position: 'absolute',
                        right: '8px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                        fontSize: '14px',
                        padding: '4px',
                        borderRadius: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'color var(--transition-fast), background var(--transition-fast)',
                      }}
                      title="Delete Session"
                      onMouseEnter={(e) => {
                        e.currentTarget.style.color = 'var(--error)';
                        e.currentTarget.style.background = 'var(--error-bg)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.color = 'var(--text-muted)';
                        e.currentTarget.style.background = 'transparent';
                      }}
                    >
                      🗑️
                    </button>
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
                <div className="flex items-center gap-12">
                  <label className="flex items-center gap-8 text-sm" style={{ cursor: 'pointer', userSelect: 'none' }}>
                    <input
                      type="checkbox"
                      checked={autoSpeak}
                      onChange={(e) => {
                        setAutoSpeak(e.target.checked);
                        if (!e.target.checked) {
                          window.speechSynthesis.cancel();
                          setSpeakingMsgId(null);
                        }
                      }}
                      style={{ cursor: 'pointer' }}
                    />
                    <span>🔊 Auto-Speak</span>
                  </label>
                  {activeSession.status === 'active' && (
                    <button className="btn btn-secondary btn-sm" onClick={endSession}>
                      End & Summarize
                    </button>
                  )}
                </div>
              </div>

              {/* Messages */}
              <div className="chat-messages" style={{ flex: 1, overflow: 'auto' }}>
                {activeSession.messages.map((msg) => (
                  <div key={msg.id} className={`message ${msg.role}`}>
                    <div className="message-avatar">
                      {msg.role === 'moderator' ? '🤖' : '👤'}
                    </div>
                    <div
                      className="message-bubble"
                      style={{
                        position: 'relative',
                        paddingRight: msg.role === 'moderator' ? '40px' : '16px',
                      }}
                    >
                      {msg.content}
                      {msg.role === 'moderator' && (
                        <button
                          onClick={() => speakText(msg.content, msg.id)}
                          style={{
                            position: 'absolute',
                            right: '8px',
                            top: '8px',
                            background: 'transparent',
                            border: 'none',
                            cursor: 'pointer',
                            fontSize: '14px',
                            opacity: speakingMsgId === msg.id ? 1 : 0.4,
                            transition: 'opacity 0.2s',
                          }}
                          title={speakingMsgId === msg.id ? "Stop Speaking" : "Read Aloud"}
                        >
                          {speakingMsgId === msg.id ? '🛑' : '🔊'}
                        </button>
                      )}
                    </div>
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
                <div className="chat-input-area" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <button
                    className={`btn ${isListening ? 'btn-danger' : 'btn-secondary'}`}
                    onClick={toggleListening}
                    style={{
                      width: '42px',
                      height: '42px',
                      padding: 0,
                      borderRadius: 'var(--radius-md)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '16px',
                      ...(isListening ? { animation: 'pulse 1.5s infinite' } : {}),
                    }}
                    title={isListening ? "Stop voice recognition" : "Speak (voice typing)"}
                    type="button"
                  >
                    {isListening ? '🛑' : '🎙️'}
                  </button>
                  <input
                    className="input"
                    placeholder={isListening ? "Listening... speak now..." : "Type your response..."}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                    disabled={sendingMsg}
                    style={{ flex: 1 }}
                  />
                  <button
                    className="btn btn-primary"
                    onClick={sendMessage}
                    disabled={sendingMsg || !message.trim()}
                    style={{ height: '42px' }}
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
