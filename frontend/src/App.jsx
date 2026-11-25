
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Plus,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Send,
  Bot,
  User,
  Sparkles,
  Trash2,
  Copy,
  Check,
  LoaderCircle,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const STORAGE_KEY = "lyftr_active_session";

const suggestions = [
  {
    title: "Explain a concept",
    prompt: "Explain how a Transformer architecture works with an example.",
  },
  {
    title: "Write some code",
    prompt: "Write a Python program to check whether a number is prime.",
  },
  {
    title: "Help me learn",
    prompt: "Create a structured roadmap for learning machine learning.",
  },
  {
    title: "Solve a problem",
    prompt: "Explain the difference between SQL joins with examples.",
  },
];

function createSessionId() {
  return crypto.randomUUID();
}

function formatDate(dateString) {
  if (!dateString) return "";

  const date = new Date(dateString);

  if (Number.isNaN(date.getTime())) return "";

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function getConversationTitle(session) {
  const title = session.title || session.last_message || "New conversation";
  return title.length > 42 ? `${title.slice(0, 42)}...` : title;
}

function MarkdownMessage({ content }) {
  return (
    <div className="markdown-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children, ...props }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              {...props}
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="markdown-table-wrapper">
              <table>{children}</table>
            </div>
          ),
          pre: ({ children }) => (
            <pre className="markdown-code-block">{children}</pre>
          ),
          code: ({ className, children, ...props }) => (
            <code className={className || "markdown-inline-code"} {...props}>
              {children}
            </code>
          ),
        }}
      >
        {content || ""}
      </ReactMarkdown>
    </div>
  );
}

function App() {
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(
    () => localStorage.getItem(STORAGE_KEY) || ""
  );
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [error, setError] = useState("");
  const [copiedMessage, setCopiedMessage] = useState(null);

  const chatAreaRef = useRef(null);
  const inputRef = useRef(null);
  const requestRef = useRef(null);

  const fetchSessions = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/sessions`);

      if (!response.ok) {
        throw new Error("Unable to load conversations.");
      }

      const data = await response.json();
      const uniqueSessions = Array.from(
        new Map(
          (data.sessions || []).map((session) => [
            session.session_id,
            session,
          ])
        ).values()
      );

      setSessions(uniqueSessions);
      return uniqueSessions;
    } catch (err) {
      console.error("Session loading error:", err);
      setError(err.message || "Unable to load conversation history.");
      return null;
    }
  }, []);

  const loadConversation = useCallback(async (sessionId) => {
    if (!sessionId) return;

    setLoadingHistory(true);
    setError("");
    requestRef.current = null;

    try {
      const response = await fetch(
        `${API_URL}/sessions/${encodeURIComponent(sessionId)}/messages`
      );

      if (response.status === 404) {
        setMessages([]);
        setActiveSession(createSessionId());
        localStorage.removeItem(STORAGE_KEY);
        return;
      }

      if (!response.ok) {
        throw new Error("Unable to open this conversation.");
      }

      const data = await response.json();

      setMessages(
        (data.messages || []).map((message, index) => ({
          ...message,
          id: `${sessionId}-${index}`,
        }))
      );

      setActiveSession(sessionId);
      localStorage.setItem(STORAGE_KEY, sessionId);
    } catch (err) {
      console.error("Conversation loading error:", err);
      setError(err.message || "Unable to open conversation.");
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function initialize() {
      const existingSessions = await fetchSessions();

      if (cancelled) return;

      if (existingSessions === null) {
        setActiveSession(
          localStorage.getItem(STORAGE_KEY) || createSessionId()
        );
        return;
      }

      const savedSession = localStorage.getItem(STORAGE_KEY);

      if (
        savedSession &&
        existingSessions.some((item) => item.session_id === savedSession)
      ) {
        await loadConversation(savedSession);
      } else {
        const firstSession = existingSessions[0];

        if (firstSession) {
          await loadConversation(firstSession.session_id);
        } else {
          const newId = createSessionId();
          setActiveSession(newId);
          setMessages([]);
          localStorage.setItem(STORAGE_KEY, newId);
        }
      }
    }

    initialize();

    return () => {
      cancelled = true;
    };
  }, [fetchSessions, loadConversation]);

  useEffect(() => {
    const container = chatAreaRef.current;
    if (!container) return;

    container.scrollTo({
      top: container.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  function newChat() {
    requestRef.current = null;

    const newId = createSessionId();

    setActiveSession(newId);
    setMessages([]);
    setInput("");
    setError("");

    localStorage.setItem(STORAGE_KEY, newId);
    inputRef.current?.focus();
  }

  async function sendMessage(event) {
    event?.preventDefault();

    const text = input.trim();

    if (!text || loading || loadingHistory) return;

    const sessionId = activeSession || createSessionId();
    const requestId = createSessionId();

    requestRef.current = requestId;

    setActiveSession(sessionId);
    localStorage.setItem(STORAGE_KEY, sessionId);

    setInput("");
    setError("");
    setLoading(true);

    setMessages((previous) => [
      ...previous,
      {
        id: `${requestId}-user`,
        role: "user",
        content: text,
      },
    ]);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: text,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "The assistant could not process your request."
        );
      }

      if (requestRef.current !== requestId) return;

      setMessages((previous) => [
        ...previous,
        {
          id: `${requestId}-assistant`,
          role: "assistant",
          content: data.reply,
          metadata: data.metadata || {},
        },
      ]);

      await fetchSessions();
    } catch (err) {
      if (requestRef.current !== requestId) return;

      setError(err.message || "Something went wrong. Please try again.");

      setMessages((previous) =>
        previous.filter((message) => message.id !== `${requestId}-user`)
      );

      setInput(text);
    } finally {
      if (requestRef.current === requestId) {
        setLoading(false);
      }
    }
  }

  async function copyMessage(content, id) {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedMessage(id);
      setTimeout(() => setCopiedMessage(null), 1500);
    } catch (err) {
      console.error("Copy failed:", err);
    }
  }

  return (
    <div className="app-shell">
      {sidebarOpen && (
        <aside className="sidebar">
          <div className="sidebar-top">
            <div className="brand">
              <div className="brand-icon">
                <Sparkles size={19} />
              </div>
              <span>
                Lyftr<span className="brand-accent"> AI</span>
              </span>
            </div>

            <button
              className="icon-btn"
              onClick={() => setSidebarOpen(false)}
              title="Close sidebar"
            >
              <PanelLeftClose size={19} />
            </button>
          </div>

          <button className="new-chat-btn" onClick={newChat}>
            <Plus size={18} />
            <span>New chat</span>
          </button>

          <div className="sidebar-section">
            <div className="section-label">Your conversations</div>

            <div className="conversation-list">
              {sessions.length === 0 ? (
                <div className="empty-history">
                  Your conversations will appear here.
                </div>
              ) : (
                sessions.map((session) => (
                  <button
                    key={session.session_id}
                    className={`conversation-item ${
                      activeSession === session.session_id ? "active" : ""
                    }`}
                    onClick={() => loadConversation(session.session_id)}
                  >
                    <MessageSquare size={16} />
                    <div className="conversation-details">
                      <span className="conversation-title">
                        {getConversationTitle(session)}
                      </span>
                      <span className="conversation-date">
                        {formatDate(session.created_at)}
                      </span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="sidebar-bottom">
            <div className="sidebar-footer">
              <span className="status-dot" />
              <span>AI services connected</span>
            </div>
          </div>
        </aside>
      )}

      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-left">
            {!sidebarOpen && (
              <button
                className="icon-btn"
                onClick={() => setSidebarOpen(true)}
                title="Open sidebar"
              >
                <PanelLeftOpen size={19} />
              </button>
            )}

            <span className="topbar-title">Chat</span>
          </div>

          <div className="topbar-right">
            <span className="model-pill">
              <span className="status-dot" />
              Lyftr AI
            </span>
            <span className="secure-label">AI Assistant</span>
          </div>
        </header>

        <section className="chat-area" ref={chatAreaRef}>
          {messages.length === 0 && !loadingHistory ? (
            <div className="welcome-screen">
              <div className="welcome-icon">
                <Sparkles size={27} />
              </div>

              <div className="eyebrow">YOUR AI ASSISTANT</div>

              <h1>How can I help you today?</h1>

              <p className="welcome-subtitle">
                Ask questions, explore ideas, write code, or learn something
                new.
              </p>

              <div className="suggestion-grid">
                {suggestions.map((suggestion) => (
                  <button
                    className="suggestion-card"
                    key={suggestion.title}
                    onClick={() => setInput(suggestion.prompt)}
                  >
                    <span>{suggestion.title}</span>
                    <p>{suggestion.prompt}</p>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="messages-container">
              {loadingHistory && (
                <div className="history-loading">
                  <LoaderCircle className="spin" size={20} />
                  Loading conversation...
                </div>
              )}

              {messages.map((message) => (
                <article
                  className={`message-row ${
                    message.role === "user" ? "user-message" : "assistant-message"
                  }`}
                  key={message.id}
                  data-testid={
                    message.role === "assistant"
                      ? "assistant-message"
                      : undefined
                  }
                >
                  <div
                    className={`message-avatar ${
                      message.role === "user" ? "user" : "assistant"
                    }`}
                  >
                    {message.role === "user" ? (
                      <User size={17} />
                    ) : (
                      <Bot size={18} />
                    )}
                  </div>

                  <div className="message-content">
                    <div className="message-author">
                      {message.role === "user" ? "You" : "Lyftr AI"}
                    </div>

                    {message.role === "assistant" ? (
                      <MarkdownMessage content={message.content} />
                    ) : (
                      <div className="user-message-text">
                        {message.content}
                      </div>
                    )}

                    {message.role === "assistant" && message.metadata && (
                      <div className="metadata-strip">
                        <span data-testid="meta-source">
                          {message.metadata.resolution_source || ""}
                        </span>
                        <span data-testid="meta-model">
                          {message.metadata.model || ""}
                        </span>
                        {message.metadata.latency_ms != null && (
                          <span data-testid="meta-latency">
                            {message.metadata.latency_ms} ms
                          </span>
                        )}
                        {message.metadata.input_tokens != null && (
                          <span data-testid="meta-input-tokens">
                            In: {message.metadata.input_tokens}
                          </span>
                        )}
                        {message.metadata.output_tokens != null && (
                          <span data-testid="meta-output-tokens">
                            Out: {message.metadata.output_tokens}
                          </span>
                        )}
                      </div>
                    )}

                    {message.role === "assistant" && (
                      <div className="message-actions">
                        <button
                          className="icon-btn small"
                          onClick={() =>
                            copyMessage(message.content, message.id)
                          }
                          title="Copy response"
                        >
                          {copiedMessage === message.id ? (
                            <Check size={15} />
                          ) : (
                            <Copy size={15} />
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                </article>
              ))}

              {loading && (
                <div className="message-row assistant-message">
                  <div className="message-avatar assistant">
                    <Bot size={18} />
                  </div>
                  <div className="message-content">
                    <div className="message-author">Lyftr AI</div>
                    <div className="typing-indicator">
                      <span />
                      <span />
                      <span />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        <footer className="composer-area">
          {error && (
            <div className="error-message">
              <AlertCircle size={16} />
              <span>{error}</span>
              <button onClick={() => setError("")} title="Dismiss">
                ×
              </button>
            </div>
          )}

          <form className="composer" onSubmit={sendMessage}>
            <textarea
              ref={inputRef}
              data-testid="chat-input"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Message Lyftr AI..."
              rows={1}
              disabled={loading || loadingHistory}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage(event);
                }
              }}
            />

            <button
              className="send-btn"
              data-testid="send-button"
              type="submit"
              disabled={!input.trim() || loading || loadingHistory}
              title="Send message"
            >
              {loading ? (
                <LoaderCircle className="spin" size={18} />
              ) : (
                <Send size={18} />
              )}
            </button>
          </form>

          <div className="composer-note">
            Lyftr AI can make mistakes. Verify important information.
          </div>
        </footer>
      </main>
    </div>
  );
}

export default App;
