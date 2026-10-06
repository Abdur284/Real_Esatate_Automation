import { useState, useEffect, useRef } from 'react';
import { db, auth } from '../firebase';
import { collection, query, where, onSnapshot, addDoc, serverTimestamp, orderBy, doc, getDoc, setDoc } from 'firebase/firestore';
import { useParams, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';

export default function Chat() {
    const { chatId } = useParams();
    const [searchParams] = useSearchParams();
    const [messages, setMessages] = useState([]);
    const [newMessage, setNewMessage] = useState('');
    const [chatData, setChatData] = useState(null);
    const scrollRef = useRef();
    const user = auth.currentUser;

    // Params for initiating a new chat
    const dealerId = searchParams.get('dealerId');
    const propertyId = searchParams.get('propertyId');
    const propertyTitle = searchParams.get('propertyTitle');

    useEffect(() => {
        if (!user) return;

        let activeChatId = chatId;

        // If no chatId but we have dealerId/propertyId, we might be starting a new one
        const initiateChat = async () => {
            if (!activeChatId && dealerId && propertyId) {
                // Generate a consistent ID for buyer-dealer-property
                const generatedId = `${user.uid}_${dealerId}_${propertyId}`;
                const chatRef = doc(db, 'chats', generatedId);
                const chatSnap = await getDoc(chatRef);

                if (!chatSnap.exists()) {
                    const dealerSnap = await getDoc(doc(db, 'users', dealerId));
                    const dealerData = dealerSnap.data();

                    await setDoc(chatRef, {
                        buyerId: user.uid,
                        buyerName: user.displayName,
                        dealerId: dealerId,
                        dealerName: dealerData?.name || 'Dealer',
                        propertyId: propertyId,
                        propertyTitle: propertyTitle || 'Property',
                        lastMessage: '',
                        lastMessageAt: serverTimestamp()
                    });
                }
                activeChatId = generatedId;
            }

            if (activeChatId) {
                // Listen to chat metadata
                onSnapshot(doc(db, 'chats', activeChatId), (d) => setChatData(d.data()));

                // Listen to messages
                const q = query(
                    collection(db, 'chats', activeChatId, 'messages'),
                    orderBy('createdAt', 'asc')
                );
                return onSnapshot(q, (snapshot) => {
                    const msgs = [];
                    snapshot.forEach(doc => msgs.push({ id: doc.id, ...doc.data() }));
                    setMessages(msgs);
                    setTimeout(() => scrollRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
                });
            }
        };

        const unsubscribe = initiateChat();
        return () => { if (typeof unsubscribe === 'function') unsubscribe(); };
    }, [chatId, user, dealerId, propertyId]);

    const handleSend = async (e) => {
        e.preventDefault();
        if (!newMessage.trim() || !user) return;

        const activeChatId = chatId || `${user.uid}_${dealerId}_${propertyId}`;

        try {
            await addDoc(collection(db, 'chats', activeChatId, 'messages'), {
                text: newMessage,
                senderId: user.uid,
                senderName: user.displayName,
                createdAt: serverTimestamp()
            });

            await setDoc(doc(db, 'chats', activeChatId), {
                lastMessage: newMessage,
                lastMessageAt: serverTimestamp()
            }, { merge: true });

            setNewMessage('');
        } catch (error) {
            console.error("Error sending message:", error);
        }
    };

    if (!user) return <div style={{ padding: '5rem', textAlign: 'center' }}>Please login to chat.</div>;

    return (
        <>
            <Navbar />
            <div style={{ height: 'calc(100vh - var(--nav-h))', display: 'flex', flexDirection: 'column', background: 'var(--bg-2)' }}>
                {/* Chat Header */}
                <div style={{ padding: '1rem 2rem', background: 'var(--surface)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '1rem', position: 'relative' }}>
                    <button
                        onClick={() => navigate(-1)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: '0.5rem', display: 'flex', alignItems: 'center' }}
                        title="Back"
                    >
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
                        </svg>
                    </button>
                    <div style={{ width: '40px', height: '40px', background: 'var(--accent)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.2rem' }}>👤</div>
                    <div>
                        <div style={{ fontWeight: 700, fontSize: '1rem' }}>
                            {user.uid === chatData?.dealerId ? chatData?.buyerName : chatData?.dealerName}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>Re: {chatData?.propertyTitle}</div>
                    </div>
                </div>

                {/* Messages Window */}
                <div style={{ flex: 1, overflowY: 'auto', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {messages.map((m, i) => (
                        <div key={i} style={{
                            alignSelf: m.senderId === user.uid ? 'flex-end' : 'flex-start',
                            maxWidth: '70%',
                            background: m.senderId === user.uid ? 'var(--accent)' : 'var(--surface)',
                            color: m.senderId === user.uid ? '#fff' : 'var(--text)',
                            padding: '0.8rem 1.2rem',
                            borderRadius: '15px',
                            borderBottomRightRadius: m.senderId === user.uid ? '2px' : '15px',
                            borderBottomLeftRadius: m.senderId !== user.uid ? '2px' : '15px',
                            boxShadow: '0 2px 10px rgba(0,0,0,0.1)'
                        }}>
                            <div style={{ fontSize: '0.9rem' }}>{m.text}</div>
                            <div style={{ fontSize: '0.65rem', marginTop: '0.4rem', opacity: 0.7, textAlign: 'right' }}>
                                {m.createdAt?.toDate ? new Date(m.createdAt.toDate()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                            </div>
                        </div>
                    ))}
                    <div ref={scrollRef} />
                </div>

                {/* Input Area */}
                <form onSubmit={handleSend} style={{ padding: '1.5rem 2rem', background: 'var(--surface)', borderTop: '1px solid var(--border)', display: 'flex', gap: '1rem' }}>
                    <input
                        className="modal-input"
                        style={{ marginBottom: 0 }}
                        placeholder="Type your message..."
                        value={newMessage}
                        onChange={e => setNewMessage(e.target.value)}
                    />
                    <button type="submit" className="chatbot-send-btn" style={{ borderRadius: '10px' }}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
                    </button>
                </form>
            </div>
        </>
    );
}
