import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import api from '../api';
import Markdown from './Markdown';


const SYSTEM_CONTEXT = `You are Haven.AI's smart assistant — a helpful, friendly AI for a real estate and home design platform called Haven.AI. 
You help users with:
- Finding properties (buying, renting, selling)
- 2D floor plan design and room layout advice
- 3D home visualization and design concepts
- Interior design suggestions (colors, furniture, style palettes)
- Construction cost estimation and renovation budgeting
- General real estate questions and guidance

Keep answers concise, helpful, and conversational. If a user asks about something unrelated to housing/design/real estate, gently redirect them to your area of expertise.`;

const QUICK_CHIPS = [
    '🏠 Find a property',
    '🏗️ 2D floor plans',
    '💰 Estimate my costs',
    '🎨 Interior design tips',
];

export default function AIChatBot() {
    const location = useLocation();
    const navigate = useNavigate();
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState([]);
    const [inputVal, setInputVal] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isMinimized, setIsMinimized] = useState(false);
    const [searchVal, setSearchVal] = useState('');
    const chatWindowRef = useRef(null);
    const inputRef = useRef(null);
    const searchRef = useRef(null);

    useEffect(() => {
        if (chatWindowRef.current) {
            chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
        }
    }, [messages, isLoading]);

    useEffect(() => {
        if (isOpen && !isMinimized) {
            setTimeout(() => inputRef.current?.focus(), 100);
        }
    }, [isOpen, isMinimized]);

    // Close on Escape
    useEffect(() => {
        const handleKey = (e) => {
            if (e.key === 'Escape' && isOpen) setIsOpen(false);
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [isOpen]);

    const sendMessage = async (text) => {
        const msg = text || inputVal.trim();
        if (!msg || isLoading) return;
        
        setInputVal('');
        setSearchVal('');
        setIsMinimized(false);
        
        // Save current history before adding the new message to state
        const currentHistory = [...messages];
        
        setMessages(prev => [...prev, { role: 'user', content: msg }]);
        setIsLoading(true);

        try {
            const data = await api.chat.send({
                message: msg,
                context: SYSTEM_CONTEXT,
                history: currentHistory
            });
            const reply = data.response || 'Sorry, I encountered an error.';
            setMessages(prev => [...prev, { role: 'assistant', content: reply }]);

            // If it's a property recommendation, notify the Properties page
            if (data.module === 'property_rec' && data.intent) {
                const event = new CustomEvent('ai-recommendation-update', {
                    detail: {
                        filters: data.intent.extracted_params,
                        raw: data
                    }
                });
                window.dispatchEvent(event);
            }
        } catch (error) {
            console.error("Connection error:", error);
            setMessages(prev => [...prev, { role: 'assistant', content: error?.message || "I couldn't reach the assistant right now. Please try again in a moment." }]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSearchSubmit = (e) => {
        e.preventDefault();
        if (searchVal.trim()) {
            setIsOpen(true);
            setIsMinimized(false);
            sendMessage(searchVal.trim());
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    };

    const clearChat = () => setMessages([]);

    const toggleOpen = () => {
        setIsOpen(prev => !prev);
        setIsMinimized(false);
    };

    if (location.pathname === '/signup') return null;

    return (
        <>
            {/* ── FLOATING SEARCH BAR ── */}
            <div className="chatbot-search-wrapper" id="ai-chatbot-search">
                <form className="chatbot-search-bar" onSubmit={handleSearchSubmit}>
                    <div className="chatbot-search-icon-wrap" onClick={toggleOpen} title="Open AI Chat">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                        </svg>
                        <span className="chatbot-search-logo">Haven<span>.AI</span></span>
                    </div>
                    <input
                        ref={searchRef}
                        className="chatbot-search-input"
                        type="text"
                        value={searchVal}
                        onChange={e => setSearchVal(e.target.value)}
                        placeholder="Ask AI anything about homes, design, costs…"
                        id="ai-search-input"
                        autoComplete="off"
                    />
                    <div className="chatbot-search-actions">
                        {isOpen && (
                            <button
                                type="button"
                                className="chatbot-search-close"
                                onClick={() => setIsOpen(false)}
                                title="Close Assistant"
                                id="ai-search-close-panel"
                            >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                                </svg>
                            </button>
                        )}
                        {searchVal && !isOpen && (
                            <button
                                type="button"
                                className="chatbot-search-clear"
                                onClick={() => setSearchVal('')}
                                title="Clear search"
                            >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                                </svg>
                            </button>
                        )}
                        <button
                            type="submit"
                            className="chatbot-search-submit"
                            title="Ask AI"
                            id="ai-search-submit-btn"
                        >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="22" y1="2" x2="11" y2="13" />
                                <polygon points="22 2 15 22 11 13 2 9 22 2" />
                            </svg>
                        </button>
                    </div>
                </form>
            </div>

            {/* ── CHAT MODAL PANEL ── */}
            {isOpen && (
                <div className={`chatbot-panel ${isMinimized ? 'minimized' : ''}`} id="ai-chat-panel">
                    {/* Header */}
                    <div className="chatbot-panel-header">
                        <div className="chatbot-panel-title">
                            <div className="chatbot-panel-dot" />
                            <span>Haven.AI Assistant</span>
                        </div>
                        <div className="chatbot-panel-actions">
                            {messages.length > 0 && (
                                <button
                                    className="chatbot-hdr-btn"
                                    onClick={clearChat}
                                    title="Clear chat"
                                    id="clear-chat-btn"
                                >
                                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                                        <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6" /><path d="M14 11v6" /><path d="M9 6V4h6v2" />
                                    </svg>
                                </button>
                            )}
                            <button
                                className="chatbot-hdr-btn"
                                onClick={() => setIsMinimized(p => !p)}
                                title={isMinimized ? 'Expand' : 'Minimize'}
                                id="minimize-chat-btn"
                            >
                                {isMinimized
                                    ? <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="18 9 12 15 6 9" /></svg>
                                    : <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="6 15 12 9 18 15" /></svg>
                                }
                            </button>
                            <button
                                className="chatbot-hdr-btn close"
                                onClick={() => { setIsOpen(false); navigate("/"); }}
                                title="Close & Go Home"
                                id="close-chat-btn"
                            >
                                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                                </svg>
                            </button>
                        </div>
                    </div>

                    {/* Chat Window */}
                    {!isMinimized && (
                        <>
                            <div className="chatbot-window" ref={chatWindowRef}>
                                {messages.length === 0 ? (
                                    <div className="chatbot-welcome">
                                        <div className="chatbot-welcome-icon">🏠</div>
                                        <h4>Hi! I'm your Haven.AI Assistant</h4>
                                        <p>Ask me anything about properties, floor plans, interior design, or cost estimation.</p>
                                        <div className="chatbot-chips">
                                            {QUICK_CHIPS.map((chip, i) => (
                                                <button
                                                    key={i}
                                                    className="chatbot-chip"
                                                    onClick={() => sendMessage(chip.replace(/^[\S]+ /, ''))}
                                                    id={`quick-chip-${i}`}
                                                >
                                                    {chip}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                ) : (
                                    messages.map((m, i) => (
                                        <div key={i} className={`chatbot-bubble ${m.role}`}>
                                            {m.role === 'assistant' && (
                                                <div className="chatbot-bubble-label">Haven.AI</div>
                                            )}
                                            <div className="chatbot-bubble-text">
                                                {m.role === 'assistant' ? <Markdown text={m.content} /> : m.content}
                                            </div>
                                        </div>
                                    ))
                                )}
                                {isLoading && (
                                    <div className="chatbot-bubble assistant">
                                        <div className="chatbot-bubble-label">Haven.AI</div>
                                        <div className="chatbot-typing">
                                            <span /><span /><span />
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Input Area */}
                            <div className="chatbot-input-area">
                                <div className="chatbot-input-row">
                                    <textarea
                                        ref={inputRef}
                                        className="chatbot-textarea"
                                        value={inputVal}
                                        onChange={e => setInputVal(e.target.value)}
                                        onKeyDown={handleKeyDown}
                                        placeholder="Type your question…"
                                        rows={1}
                                        id="chatbot-message-input"
                                    />
                                    <button
                                        className="chatbot-send-btn"
                                        onClick={() => sendMessage()}
                                        disabled={isLoading}
                                        id="chatbot-send-btn"
                                    >
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                            <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
                                        </svg>
                                    </button>
                                </div>
                                <p className="chatbot-hint">Press Enter to send · Shift+Enter for new line</p>
                            </div>
                        </>
                    )}
                </div>
            )}
        </>
    );
}
