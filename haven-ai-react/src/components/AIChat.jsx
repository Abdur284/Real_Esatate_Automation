import { useEffect, useRef, useState } from 'react';
import api from '../api';
import Markdown from './Markdown';

// Using the centralized API module for backend calls

export default function AIChat({ title, icon, welcomeText, placeholder, chips, systemContext }) {
    const chatWindowRef = useRef(null);
    const textareaRef = useRef(null);
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [inputVal, setInputVal] = useState('');

    useEffect(() => {
        if (chatWindowRef.current) {
            chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
        }
    }, [messages, isLoading]);

    const sendMessage = async (text) => {
        const msg = text || inputVal.trim();
        if (!msg || isLoading) return;
        setInputVal('');
        setMessages(prev => [...prev, { role: 'user', content: msg }]);
        setIsLoading(true);
        try {
            const data = await api.chat.send({
                message: msg,
                context: systemContext || '',
            });
            const reply = data.response || 'Sorry, I encountered an error.';
            setMessages(prev => [...prev, { role: 'assistant', content: reply }]);
        } catch (error) {
            console.error("Connection error:", error);
            setMessages(prev => [...prev, { role: 'assistant', content: error?.message || "I couldn't reach the assistant right now. Please try again in a moment." }]);
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
                        {m.role === 'assistant' ? <Markdown text={m.content} /> : m.content}
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
