import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
    addDoc, collection, doc, getDoc, onSnapshot, orderBy, query, serverTimestamp, setDoc, updateDoc, where,
} from 'firebase/firestore';
import { db } from '../firebase';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../components/Toast';

// Buyer ↔ dealer messaging. One document per buyer/dealer/property in
// `chats` (id = buyerId_dealerId_propertyId) with a `messages` subcollection;
// the Firestore rules only let the two participants read or write it.

const chatIdFor = (buyerId, dealerId, propertyId) => `${buyerId}_${dealerId}_${propertyId}`;

function timeLabel(ts) {
    const d = ts?.toDate ? ts.toDate() : null;
    return d ? d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
}

/** Conversations the user takes part in, newest first (as buyer and as dealer). */
function Inbox({ uid }) {
    const navigate = useNavigate();
    const [asBuyer, setAsBuyer] = useState(null);
    const [asDealer, setAsDealer] = useState(null);

    useEffect(() => {
        const listen = (field, set) => onSnapshot(
            query(collection(db, 'chats'), where(field, '==', uid)),
            (snap) => set(snap.docs.map((d) => ({ id: d.id, ...d.data() }))),
            () => set([]),
        );
        const a = listen('buyerId', setAsBuyer);
        const b = listen('dealerId', setAsDealer);
        return () => { a(); b(); };
    }, [uid]);

    if (asBuyer === null || asDealer === null) {
        return <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--text-3)' }}>Loading conversations…</div>;
    }
    const chats = [...asBuyer, ...asDealer]
        .sort((x, y) => (y.lastMessageAt?.toMillis?.() || 0) - (x.lastMessageAt?.toMillis?.() || 0));

    return (
        <div className="page-content" style={{ maxWidth: '760px' }}>
            <h1 style={{ fontFamily: 'Syne, sans-serif', marginBottom: '1.5rem' }}>Messages</h1>
            {chats.length === 0 ? (
                <div style={{ padding: '3rem', textAlign: 'center', background: 'var(--surface)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                    <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>💬</div>
                    <p style={{ color: 'var(--text-3)', marginBottom: '1.5rem' }}>No conversations yet. Contact a dealer from any property listing.</p>
                    <button className="btn-cta" onClick={() => navigate('/properties')}>Browse properties</button>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {chats.map((c) => {
                        const other = c.buyerId === uid ? c.dealerName : c.buyerName;
                        return (
                            <button key={c.id} onClick={() => navigate(`/chat/${c.id}`)}
                                style={{ textAlign: 'left', padding: '1rem 1.25rem', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '12px', cursor: 'pointer', color: 'var(--text)', font: 'inherit' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                                    <strong>{other || 'User'}</strong>
                                    <span style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>{timeLabel(c.lastMessageAt)}</span>
                                </div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--accent)', margin: '0.2rem 0 0.4rem' }}>Re: {c.propertyTitle}</div>
                                <div style={{ fontSize: '0.85rem', color: 'var(--text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {c.lastMessage || 'Conversation started'}
                                </div>
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

export default function Chat() {
    const { chatId: routeChatId } = useParams();
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const toast = useToast();
    const { user, profile } = useAuth();
    const [chatId, setChatId] = useState(routeChatId || null);
    const [chatData, setChatData] = useState(null);
    const [messages, setMessages] = useState([]);
    const [newMessage, setNewMessage] = useState('');
    const [error, setError] = useState(null);
    const [sending, setSending] = useState(false);
    const scrollRef = useRef(null);

    const propertyId = searchParams.get('propertyId');

    useEffect(() => { setChatId(routeChatId || null); }, [routeChatId]);

    // Coming from a listing (?propertyId=…): open the existing conversation
    // with its dealer, or create it. Dealer and title come from the listing.
    useEffect(() => {
        if (routeChatId || !propertyId || !user) return;
        let alive = true;
        (async () => {
            try {
                const propSnap = await getDoc(doc(db, 'properties', propertyId));
                if (!propSnap.exists()) throw new Error('This listing no longer exists.');
                const prop = propSnap.data();
                if (!prop.dealerId) throw new Error('This listing has no dealer to contact.');
                if (prop.dealerId === user.uid) throw new Error('This is your own listing.');
                const id = chatIdFor(user.uid, prop.dealerId, propertyId);
                const ref = doc(db, 'chats', id);
                let exists = false;
                try { exists = (await getDoc(ref)).exists(); } catch { exists = false; }
                if (!exists) {
                    await setDoc(ref, {
                        buyerId: user.uid,
                        buyerName: profile?.name || user.displayName || 'Buyer',
                        dealerId: prop.dealerId,
                        dealerName: prop.dealerName || 'Dealer',
                        propertyId,
                        propertyTitle: prop.title || 'Property',
                        lastMessage: '',
                        lastMessageAt: serverTimestamp(),
                    });
                }
                if (alive) navigate(`/chat/${id}`, { replace: true });
            } catch (e) {
                if (alive) setError(e.message || 'Could not open this conversation.');
            }
        })();
        return () => { alive = false; };
    }, [routeChatId, propertyId, user, profile, navigate]);

    // Live conversation + messages.
    useEffect(() => {
        if (!chatId || !user) return;
        const unsubChat = onSnapshot(doc(db, 'chats', chatId),
            (d) => setChatData(d.exists() ? d.data() : null),
            () => setError('You do not have access to this conversation.'));
        const unsubMsgs = onSnapshot(
            query(collection(db, 'chats', chatId, 'messages'), orderBy('createdAt', 'asc')),
            (snap) => setMessages(snap.docs.map((d) => ({ id: d.id, ...d.data() }))),
            () => setError('You do not have access to this conversation.'));
        return () => { unsubChat(); unsubMsgs(); };
    }, [chatId, user]);

    useEffect(() => { scrollRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

    const handleSend = async (e) => {
        e.preventDefault();
        const text = newMessage.trim();
        if (!text || !chatId || sending) return;
        setSending(true);
        try {
            await addDoc(collection(db, 'chats', chatId, 'messages'), {
                text,
                senderId: user.uid,
                senderName: profile?.name || user.displayName || 'User',
                createdAt: serverTimestamp(),
            });
            await updateDoc(doc(db, 'chats', chatId), { lastMessage: text.slice(0, 200), lastMessageAt: serverTimestamp() });
            setNewMessage('');
        } catch {
            toast.error('Your message could not be sent. Please try again.');
        } finally {
            setSending(false);
        }
    };

    if (error) {
        return (
            <div className="page-content" style={{ padding: '6rem 2rem', textAlign: 'center' }}>
                <p style={{ color: 'var(--text-2)', marginBottom: '1.5rem' }}>{error}</p>
                <button className="btn-cta" onClick={() => navigate('/chat')}>Back to messages</button>
            </div>
        );
    }
    if (!chatId) {
        if (propertyId) return <div style={{ padding: '5rem', textAlign: 'center', color: 'var(--text-3)' }}>Opening conversation…</div>;
        return <Inbox uid={user.uid} />;
    }

    const otherName = user.uid === chatData?.dealerId ? chatData?.buyerName : chatData?.dealerName;

    return (
        <div style={{ height: 'calc(100vh - var(--nav-h))', display: 'flex', flexDirection: 'column', background: 'var(--bg-2)' }}>
            {/* Chat Header */}
            <div style={{ padding: '1rem 2rem', background: 'var(--surface)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '1rem', position: 'relative' }}>
                <button
                    onClick={() => navigate('/chat')}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: '0.5rem', display: 'flex', alignItems: 'center' }}
                    title="All messages" aria-label="All messages"
                >
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
                    </svg>
                </button>
                <div style={{ width: '40px', height: '40px', background: 'var(--accent)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.2rem' }}>👤</div>
                <div>
                    <div style={{ fontWeight: 700, fontSize: '1rem' }}>{otherName || '…'}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>Re: {chatData?.propertyTitle}</div>
                </div>
            </div>

            {/* Messages Window */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {messages.length === 0 && (
                    <div style={{ textAlign: 'center', color: 'var(--text-3)', fontSize: '0.85rem', marginTop: '2rem' }}>No messages yet. Say hello! 👋</div>
                )}
                {messages.map((m) => {
                    const mine = m.senderId === user.uid;
                    return (
                        <div key={m.id} style={{
                            alignSelf: mine ? 'flex-end' : 'flex-start',
                            maxWidth: '70%',
                            background: mine ? 'var(--accent)' : 'var(--surface)',
                            color: mine ? '#fff' : 'var(--text)',
                            padding: '0.8rem 1.2rem',
                            borderRadius: '15px',
                            borderBottomRightRadius: mine ? '2px' : '15px',
                            borderBottomLeftRadius: !mine ? '2px' : '15px',
                            boxShadow: '0 2px 10px rgba(0,0,0,0.1)'
                        }}>
                            <div style={{ fontSize: '0.9rem', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{m.text}</div>
                            <div style={{ fontSize: '0.65rem', marginTop: '0.4rem', opacity: 0.7, textAlign: 'right' }}>
                                {m.createdAt?.toDate ? m.createdAt.toDate().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '…'}
                            </div>
                        </div>
                    );
                })}
                <div ref={scrollRef} />
            </div>

            {/* Input Area */}
            <form onSubmit={handleSend} style={{ padding: '1.5rem 2rem', background: 'var(--surface)', borderTop: '1px solid var(--border)', display: 'flex', gap: '1rem' }}>
                <input
                    className="modal-input"
                    style={{ marginBottom: 0 }}
                    placeholder="Type your message..."
                    aria-label="Message"
                    maxLength={2000}
                    value={newMessage}
                    onChange={e => setNewMessage(e.target.value)}
                />
                <button type="submit" className="chatbot-send-btn" style={{ borderRadius: '10px' }} disabled={sending} aria-label="Send">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
                </button>
            </form>
        </div>
    );
}
