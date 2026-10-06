import { useEffect, useRef, useState } from 'react';
import api from '../api';

// Using the centralized API module for backend calls

export default function AIChat({ title, icon, welcomeText, placeholder, chips, systemContext }) {
    const chatWindowRef = useRef(null);
    const textareaRef = useRef(null);
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [inputVal, setInputVal] = useState('');

    const [isVisible, setIsVisible] = useState(true);

    useEffect(() => {
        if (chatWindowRef.current) {
            chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
        }
    }, [messages, isLoading, isVisible]);

    if (!isVisible) return (
        <button
            className="btn-ghost"
            style={{ marginBottom: '2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            onClick={() => setIsVisible(true)}
        >
        </button>
    );

    const sendMessage = async (text) => {
        const msg = text || inputVal.trim();
        if (!msg || isLoading) return;
        setInputVal('');
        setMessages(prev => [...prev, { role: 'user', content: msg }]);
        setIsLoading(true);
        try {
            const data = await api.chat.send({
                userId: 'guest',
                message: msg,
                context: systemContext || '',
            });
            const reply = data.response || 'Sorry, I encountered an error.';
            setMessages(prev => [...prev, { role: 'assistant', content: reply }]);
        } catch (error) {
            console.error("Connection error:", error);
            setMessages(prev => [...prev, { role: 'assistant', content: "I'm having trouble connecting to the Haven AI backend. Please make sure the server is running." }]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    };

    return (
        <div className="ai-card">
            <div className="ai-card-header">
                <div className="ai-card-title">{title}</div>
                <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div className="ai-status">AI Online</div>
                    <button
                        onClick={() => setIsVisible(false)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: '0.2rem', display: 'flex' }}
                        title="Close Chat"
                    >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                    </button>
                </div>
            </div>
            <div className="ai-chat-window" ref={chatWindowRef}>
                {messages.length === 0 && (
                    <div className="ai-welcome">
                        <div className="ai-welcome-icon">{icon}</div>
                        <h3>{title}</h3>
                        <p>{welcomeText}</p>
                    </div>
                )}
                {messages.map((m, i) => (
                    <div key={i} className={`chat-bubble ${m.role}`}>
                        {m.role === 'assistant' && <span className="bubble-label">AI Assistant</span>}
                        {m.content.split('\n').map((line, li) => (
                            <span key={li}>{line}{li < m.content.split('\n').length - 1 && <br />}</span>
                        ))}
                    </div>
                ))}
                {isLoading && (
                    <div className="typing-indicator">
                        <span /><span /><span />
                    </div>
                )}
            </div>
            <div className="ai-input-area">
                <div className="ai-input-row">
                    <textarea
                        ref={textareaRef}
                        className="ai-textarea"
                        value={inputVal}
                        onChange={e => setInputVal(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={placeholder}
                        rows={1}
                    />
                    <button className="send-btn" onClick={() => sendMessage()} disabled={isLoading}>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                            <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
                        </svg>
                    </button>
                </div>
                {chips && chips.length > 0 && (
                    <div className="prompt-chips">
                        {chips.map((chip, i) => (
                            <button key={i} className="chip" onClick={() => sendMessage(chip)}>{chip}</button>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
