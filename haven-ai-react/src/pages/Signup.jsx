import { useState, useEffect, useRef, useCallback } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

// ─── FIREBASE REST API CONFIG ────────────────────────────────────────────────
const firebaseConfig = {
    apiKey: "AIzaSyAJURwVDVWEXl_9NbebMDRxyIgriWGfL7Q",
    authDomain: "website-d8f60.firebaseapp.com",
    projectId: "website-d8f60",
    storageBucket: "website-d8f60.firebasestorage.app",
    messagingSenderId: "242761359928",
    appId: "1:242761359928:web:1f170fb87244c4af5c3ccd"
};
const AUTH_URL = "https://identitytoolkit.googleapis.com/v1";
const DB_URL = `https://firestore.googleapis.com/v1/projects/${firebaseConfig.projectId}/databases/(default)/documents`;

// ─── REST HELPERS — AUTH ──────────────────────────────────────────────────────
const authFetch = async (endpoint, body) => {
    const res = await fetch(`${AUTH_URL}/accounts:${endpoint}?key=${firebaseConfig.apiKey}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error.message);
    return data;
};

const restSignup = (email, password) => authFetch("signUp", { email, password, returnSecureToken: true });
const restLogin = (email, password) => authFetch("signInWithPassword", { email, password, returnSecureToken: true });
const restUpdateProfile = (idToken, displayName) => authFetch("update", { idToken, displayName, returnSecureToken: true });
const restGetUserInfo = (idToken) => authFetch("lookup", { idToken });

// ─── REST HELPERS — FIRESTORE ─────────────────────────────────────────────────
const toFs = (v) => {
    if (v === null || v === undefined) return { nullValue: null };
    if (typeof v === "string") return { stringValue: v };
    if (typeof v === "number") return { doubleValue: v };
    if (typeof v === "boolean") return { booleanValue: v };
    if (Array.isArray(v)) return { arrayValue: { values: v.map(toFs) } };
    if (v instanceof Date) return { timestampValue: v.toISOString() };
    if (typeof v === "object") return { mapValue: { fields: Object.fromEntries(Object.entries(v).map(([k, val]) => [k, toFs(val)])) } };
    return { stringValue: String(v) };
};

const fromFs = (f) => {
    if (!f) return null;
    if ("stringValue" in f) return f.stringValue;
    if ("doubleValue" in f) return parseFloat(f.doubleValue);
    if ("integerValue" in f) return parseInt(f.integerValue);
    if ("booleanValue" in f) return f.booleanValue;
    if ("timestampValue" in f) return f.timestampValue;
    if ("arrayValue" in f) return (f.arrayValue.values || []).map(fromFs);
    if ("mapValue" in f) return Object.fromEntries(Object.entries(f.mapValue.fields || {}).map(([k, v]) => [k, fromFs(v)]));
    return null;
};

const dbFetch = async (path, method = "GET", body = null, token = null) => {
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${DB_URL}${path}`, {
        method,
        headers,
        ...(body && { body: JSON.stringify(body) })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error.message);
    return data;
};

const restGetDoc = async (col, id, token = null) => {
    try {
        const d = await dbFetch(`/${col}/${id}`, "GET", null, token);
        return fromFs({ mapValue: { fields: d.fields } });
    } catch (e) { if (e.message.includes("NOT_FOUND")) return null; throw e; }
};

const restSetDoc = (col, id, data, token = null) => {
    const fields = Object.fromEntries(Object.entries(data).map(([k, v]) => [k, toFs(v)]));
    return dbFetch(`/${col}/${id}`, "PATCH", { fields }, token);
};

const restAddDoc = (col, data, token = null) => {
    const fields = Object.fromEntries(Object.entries(data).map(([k, v]) => [k, toFs(v)]));
    return dbFetch(`/${col}`, "POST", { fields }, token);
};

const restQuery = async (colPath, filters = [], token = null) => {
    const parts = colPath.split("/");
    const colId = parts.pop();
    const parentPath = parts.length ? `/${parts.join("/")}` : "";
    
    const body = { structuredQuery: { from: [{ collectionId: colId }], where: filters.length ? { compositeFilter: { op: "AND", filters: filters.map(f => ({ fieldFilter: { field: { fieldPath: f[0] }, op: f[1], value: toFs(f[2]) } })) } } : undefined } };
    const res = await dbFetch(`${parentPath}:runQuery`, "POST", body, token);
    return (res || []).filter(r => r.document).map(r => ({ ...fromFs({ mapValue: { fields: r.document.fields } }), id: r.document.name.split("/").pop() }));
};

// ─── STATIC DATA ─────────────────────────────────────────────────────────────
const PROPERTIES = [
    { id: 1, emoji: "🏡", title: "5 Marla House — DHA Phase 6", price: "₨ 2.1 Cr", loc: "DHA Phase 6, Lahore", type: "sale", tags: ["5 Marla", "4 Beds", "3 Bath", "Corner Plot"], desc: "Beautifully renovated corner plot house in DHA Phase 6. Modern kitchen, large lounge, servant quarters, and 2-car parking.", dealer: "Ahmad Raza", dealerGrad: "linear-gradient(135deg,#10b981,#059669)", dealerTag: "DHA Properties — Lahore" },
    { id: 2, emoji: "🏢", title: "10 Marla House — Bahria Town", price: "₨ 3.8 Cr", loc: "Bahria Town Phase 8, Islamabad", type: "sale", tags: ["10 Marla", "5 Beds", "4 Bath", "Garden"], desc: "Spacious double-storey house in Bahria Town with a lush garden. Prime location near commercial market.", dealer: "Sara Khan", dealerGrad: "linear-gradient(135deg,#8b5cf6,#6d28d9)", dealerTag: "Bahria Realty — Islamabad" },
    { id: 3, emoji: "🏠", title: "1 Kanal Farmhouse — Bedian Road", price: "₨ 1.2 Cr", loc: "Bedian Road, Lahore", type: "sale", tags: ["1 Kanal", "6 Beds", "5 Bath", "Pool"], desc: "Stunning farmhouse with a private swimming pool, open lawn, and fully furnished interiors.", dealer: "Usman Malik", dealerGrad: "linear-gradient(135deg,#f59e0b,#d97706)", dealerTag: "Luxury Estates — Lahore" },
    { id: 4, emoji: "🏗", title: "5 Marla Plot — Park View City", price: "₨ 85 Lac", loc: "Park View City, Islamabad", type: "sale", tags: ["5 Marla", "Plot", "CDA Approved", "Corner"], desc: "CDA approved residential plot in fast-developing Park View City. Ideal investment with all utilities available.", dealer: "Ali Hassan", dealerGrad: "linear-gradient(135deg,#3b82f6,#1d4ed8)", dealerTag: "Park View City — Islamabad" },
    { id: 5, emoji: "🏘", title: "2 Bed Apartment — F-11 Markaz", price: "₨ 45K/mo", loc: "F-11 Markaz, Islamabad", type: "rent", tags: ["1050 sqft", "2 Beds", "2 Bath", "Elevator"], desc: "Modern apartment in a gated community. 24/7 security, standby generator, and dedicated parking.", dealer: "Sara Khan", dealerGrad: "linear-gradient(135deg,#8b5cf6,#6d28d9)", dealerTag: "Bahria Realty — Islamabad" },
    { id: 6, emoji: "🏬", title: "Commercial Shop — Blue Area", price: "₨ 2.5 Cr", loc: "Blue Area, Islamabad", type: "sale", tags: ["800 sqft", "Ground Floor", "Main Blvd", "Parking"], desc: "Prime commercial shop in Blue Area on the main road. High foot traffic location.", dealer: "Ahmad Raza", dealerGrad: "linear-gradient(135deg,#10b981,#059669)", dealerTag: "DHA Properties — Lahore" },
];

// ─── HELPERS ─────────────────────────────────────────────────────────────────
const initials = n => (n || "?").split(" ").map(w => w[0]).filter(c => /[a-zA-Z]/.test(c)).join("").toUpperCase().slice(0, 2);
const timeAgo = d => { const s = Math.floor((Date.now() - d) / 1000); if (s < 60) return "now"; if (s < 3600) return Math.floor(s / 60) + "m"; if (s < 86400) return Math.floor(s / 3600) + "hr"; return Math.floor(s / 86400) + "d"; };
const buildConvId = (uid, dealer, prop) => { const safe = s => s.replace(/[^a-zA-Z0-9]/g, "_").slice(0, 30); return `${uid}__${safe(dealer)}__${safe(prop)}`; };
const fmtCNIC = v => { let d = v.replace(/\D/g, ""); if (d.length > 5) d = d.slice(0, 5) + "-" + d.slice(5); if (d.length > 13) d = d.slice(0, 13) + "-" + d.slice(13, 14); return d; };
const fmtMobile = v => { let d = v.replace(/\D/g, ""); if (d.length > 4) d = d.slice(0, 4) + "-" + d.slice(4, 11); return d; };

// ─── DESIGN TOKENS ───────────────────────────────────────────────────────────
const C = { bg: "#07090e", bg2: "#0c0f18", surface: "#111521", surface2: "#181d2e", border: "rgba(255,255,255,0.06)", border2: "rgba(255,255,255,0.10)", text: "#eef0f8", text2: "#8892aa", text3: "#454e64", accent: "#3b82f6", accent2: "#60a5fa", green: "#10b981" };

const inpStyle = (hasErr = false) => ({ width: "100%", background: C.surface, border: `1px solid ${hasErr ? "#ef4444" : C.border2}`, borderRadius: "11px", padding: "0.75rem 0.9rem", color: C.text, fontFamily: "inherit", fontSize: "0.88rem", outline: "none", boxSizing: "border-box" });
const miniInp = { width: "100%", background: C.bg2, border: `1px solid ${C.border2}`, borderRadius: "9px", padding: "0.65rem 0.85rem", color: C.text, fontFamily: "inherit", fontSize: "0.82rem", outline: "none", marginBottom: "0.7rem", boxSizing: "border-box" };
const miniSel = { ...miniInp, appearance: "none", cursor: "pointer" };

// ─── AUTH FIELD — defined at module level to prevent remount on each render ──
function AuthField({ label, fieldKey, type = "text", value, error, onChange, onSubmit, transform, showStrength }) {
    let s = 0;
    if (showStrength && value) { if (value.length >= 8) s++; if (/[A-Z]/.test(value)) s++; if (/[0-9]/.test(value)) s++; if (/[^A-Za-z0-9]/.test(value)) s++; }
    const strengthCols = ["", "#ef4444", "#f59e0b", "#3b82f6", "#10b981"];
    const strengthLabs = ["", "Weak", "Fair", "Good", "Strong"];
    return (
        <div style={{ marginBottom: "0.9rem" }}>
            <label style={{ display: "block", fontSize: "0.72rem", fontWeight: 600, color: C.text2, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: "0.4rem" }}>{label}</label>
            <input
                type={type}
                value={value}
                placeholder={label}
                style={inpStyle(!!error)}
                onChange={e => onChange(fieldKey, transform ? transform(e.target.value) : e.target.value)}
                onKeyDown={e => e.key === "Enter" && onSubmit()}
            />
            {error && <div style={{ fontSize: "0.7rem", color: "#ef4444", marginTop: "0.25rem" }}>{error}</div>}
            {showStrength && value && (
                <div>
                    <div style={{ display: "flex", gap: 4, marginTop: 6 }}>
                        {[0, 1, 2, 3].map(i => <div key={i} style={{ flex: 1, height: 3, borderRadius: 2, background: i < s ? strengthCols[s] : C.border2, transition: "background 0.3s" }} />)}
                    </div>
                    <div style={{ fontSize: "0.67rem", color: strengthCols[s], marginTop: 3 }}>{strengthLabs[s]}</div>
                </div>
            )}
        </div>
    );
}

// ─── TOAST ───────────────────────────────────────────────────────────────────
function Toast({ t }) {
    if (!t) return null;
    return (
        <div style={{ position: "fixed", bottom: "2rem", right: "2rem", zIndex: 500, background: C.surface, border: "1px solid rgba(16,185,129,0.3)", borderRadius: "14px", padding: "1rem 1.25rem", display: "flex", alignItems: "center", gap: "0.75rem", boxShadow: "0 20px 60px rgba(0,0,0,0.4)", maxWidth: "320px" }}>
            <span style={{ fontSize: "1.3rem" }}>{t.icon || "✅"}</span>
            <div><strong style={{ display: "block", fontSize: "0.85rem", color: C.text }}>{t.title}</strong><span style={{ fontSize: "0.8rem", color: C.text2 }}>{t.sub}</span></div>
        </div>
    );
}

// ─── CHAT MODAL ──────────────────────────────────────────────────────────────
function ChatModal({ convId, headerName, headerGrad, headerProp, currentUser, onClose }) {
    const [msgs, setMsgs] = useState([]);
    const [input, setInput] = useState("");
    const [status, setStatus] = useState("Connecting…");
    const endRef = useRef(null);
    const unsubRef = useRef(null);

    useEffect(() => {
        if (!convId) return;
        let alive = true;
        let pollTimer = null;

        const fetchMsgs = async () => {
            try {
                // Ensure conversation exists
                const snap = await restGetDoc("conversations", convId, currentUser.idToken);
                if (!snap) {
                    await restSetDoc("conversations", convId, {
                        buyerUid: currentUser.uid,
                        buyerName: currentUser.name,
                        dealerName: headerName,
                        propertyTitle: (headerProp || "").replace("Re: ", ""),
                        lastMessage: "",
                        lastAt: new Date().toISOString(),
                        unreadDealer: 0,
                        unreadBuyer: 0
                    }, currentUser.idToken);
                } else {
                    // Clear unread mark for current user
                    await restSetDoc("conversations", convId, { unreadBuyer: 0 }, currentUser.idToken);
                }

                // Fetch messages
                const res = await restQuery(`conversations/${convId}/messages`, [], currentUser.idToken);
                if (alive) {
                    setStatus(null);
                    setMsgs(res.sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt)));
                }
            } catch (e) {
                if (alive) setStatus("⚠ " + e.message);
            }
        };

        fetchMsgs();
        pollTimer = setInterval(fetchMsgs, 4000); // Poll every 4 seconds

        return () => { alive = false; clearInterval(pollTimer); };
    }, [convId]);

    useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

    const send = async () => {
        const text = input.trim(); if (!text || !convId) return; setInput("");
        const now = new Date().toISOString();
        
        // Optimistic UI update so the sender sees the message immediately
        setMsgs(prev => [...prev, {
            id: Math.random().toString(),
            senderUid: currentUser.uid,
            senderName: currentUser.name,
            text,
            createdAt: now
        }]);

        try {
            await restAddDoc(`conversations/${convId}/messages`, {
                senderUid: currentUser.uid,
                senderName: currentUser.name,
                text,
                createdAt: now
            }, currentUser.idToken);
            await restSetDoc("conversations", convId, {
                lastMessage: text,
                lastAt: now,
                ...(currentUser.role === "buyer" ? { unreadDealer: 1 } : { unreadBuyer: 1 })
            }, currentUser.idToken);
        } catch (e) { console.error(e); }
    };

    return (
        <div style={{ position: "fixed", inset: 0, zIndex: 300, background: "rgba(0,0,0,0.7)", backdropFilter: "blur(6px)", display: "flex", alignItems: "center", justifyContent: "center" }} onClick={e => e.target === e.currentTarget && onClose()}>
            <div style={{ width: "100%", maxWidth: "460px", height: "580px", background: C.surface, border: `1px solid ${C.border2}`, borderRadius: "20px", display: "flex", flexDirection: "column", boxShadow: "0 40px 120px rgba(0,0,0,0.6)" }}>
                <div style={{ padding: "1rem 1.25rem", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", gap: "0.85rem" }}>
                    <div style={{ width: 40, height: 40, borderRadius: "50%", background: headerGrad || C.accent, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, color: "#fff", flexShrink: 0 }}>{initials(headerName)}</div>
                    <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 700, fontSize: "0.92rem", color: C.text }}>{headerName}</div>
                        <div style={{ fontSize: "0.68rem", color: C.green }}>● Online</div>
                        {headerProp && <div style={{ fontSize: "0.7rem", color: C.text3, fontStyle: "italic" }}>{headerProp}</div>}
                    </div>
                    <button onClick={onClose} style={{ background: "none", border: "none", color: C.text3, cursor: "pointer", fontSize: "1.2rem" }}>✕</button>
                </div>
                <div style={{ flex: 1, overflowY: "auto", padding: "1rem", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                    {status && <div style={{ textAlign: "center", color: C.text3, fontSize: "0.75rem", padding: "1rem" }}>{status}</div>}
                    {!status && msgs.length === 0 && <div style={{ textAlign: "center", color: C.text3, fontSize: "0.75rem", padding: "1rem" }}>No messages yet. Say hello! 👋</div>}
                    {msgs.map(m => {
                        const isMe = m.senderUid === currentUser.uid;
                        const time = m.createdAt ? new Date(m.createdAt).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }) : "…";
                        return (
                            <div key={m.id} style={{ display: "flex", flexDirection: "column", maxWidth: "75%", alignSelf: isMe ? "flex-end" : "flex-start" }}>
                                <div style={{ padding: "0.65rem 0.9rem", borderRadius: isMe ? "14px 14px 4px 14px" : "4px 14px 14px 14px", fontSize: "0.82rem", lineHeight: 1.55, background: isMe ? C.accent : C.surface2, color: C.text }}>{m.text}</div>
                                <div style={{ fontSize: "0.62rem", color: C.text3, marginTop: "0.25rem", textAlign: isMe ? "right" : "left" }}>{time}</div>
                            </div>
                        );
                    })}
                    <div ref={endRef} />
                </div>
                <div style={{ padding: "0.9rem 1rem", borderTop: `1px solid ${C.border}`, display: "flex", gap: "0.6rem", alignItems: "center" }}>
                    <input style={{ flex: 1, background: C.bg2, border: `1px solid ${C.border2}`, borderRadius: "100px", padding: "0.6rem 1rem", color: C.text, fontFamily: "inherit", fontSize: "0.82rem", outline: "none" }} value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && send()} placeholder="Type a message…" />
                    <button onClick={send} style={{ width: 36, height: 36, borderRadius: "50%", background: C.accent, border: "none", cursor: "pointer", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>➤</button>
                </div>
            </div>
        </div>
    );
}

// ─── PROPERTY DETAIL MODAL ───────────────────────────────────────────────────
function PropModal({ prop, onClose, onContact }) {
    if (!prop) return null;
    return (
        <div style={{ position: "fixed", inset: 0, zIndex: 200, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)", display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }} onClick={e => e.target === e.currentTarget && onClose()}>
            <div style={{ background: C.surface, border: `1px solid ${C.border2}`, borderRadius: "20px", width: "100%", maxWidth: "560px", maxHeight: "90vh", overflowY: "auto" }}>
                <div style={{ aspectRatio: "16/9", background: "linear-gradient(135deg,#1a2a4a,#0f1a2e)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "5rem", borderRadius: "18px 18px 0 0" }}>{prop.emoji}</div>
                <div style={{ padding: "1.5rem" }}>
                    <div style={{ fontWeight: 800, fontSize: "1.2rem", color: C.text, marginBottom: "0.3rem" }}>{prop.title}</div>
                    <div style={{ fontWeight: 800, fontSize: "1.4rem", color: C.accent2, marginBottom: "0.6rem" }}>{prop.price}</div>
                    <div style={{ fontSize: "0.8rem", color: C.text3, marginBottom: "1rem" }}>📍 {prop.loc}</div>
                    
                    {/* NEW: Map & Directions Section in Modal */}
                    <div style={{ marginBottom: '1.25rem', background: 'rgba(255,255,255,0.03)', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border)' }}>
                        {prop.mapImage && (
                            <img src={prop.mapImage} alt="Map Area" style={{ width: '100%', borderRadius: '8px', marginBottom: '1rem', border: '1px solid var(--border)' }} />
                        )}
                        <button 
                            onClick={() => prop.mapUrl ? window.open(prop.mapUrl, '_blank') : alert("Please contact dealer for location.")}
                            style={{ width: '100%', padding: '0.7rem', background: prop.mapUrl ? 'var(--accent)' : 'var(--text-3)', border: 'none', borderRadius: '8px', color: '#fff', fontSize: '0.8rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
                        >
                            {prop.mapUrl ? '🚀 Get Live Directions' : 'Location'}
                        </button>
                    </div>

                    <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", marginBottom: "1rem" }}>
                        {prop.tags.map(t => <span key={t} style={{ background: C.surface2, border: `1px solid ${C.border}`, borderRadius: "100px", padding: "0.15rem 0.55rem", fontSize: "0.65rem", color: C.text2 }}>{t}</span>)}
                    </div>
                    <p style={{ fontSize: "0.82rem", color: C.text2, lineHeight: 1.7, marginBottom: "1.25rem" }}>{prop.desc}</p>
                    <div style={{ background: C.surface2, border: `1px solid ${C.border2}`, borderRadius: "12px", padding: "1rem", display: "flex", alignItems: "center", gap: "0.9rem", marginBottom: "1rem" }}>
                        <div style={{ width: 44, height: 44, borderRadius: "50%", background: prop.dealerGrad || C.accent, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, color: "#fff", flexShrink: 0 }}>{initials(prop.dealer || "D")}</div>
                        <div style={{ flex: 1 }}>
                            <div style={{ fontSize: "0.85rem", fontWeight: 600, color: C.text }}>{prop.dealer || "Dealer"}</div>
                            <div style={{ fontSize: "0.68rem", color: C.text3 }}>{prop.dealerTag || "Verified Dealer"}</div>
                        </div>
                        <span style={{ fontSize: "0.65rem", fontWeight: 700, background: "rgba(16,185,129,0.12)", color: "#34d399", border: "1px solid rgba(16,185,129,0.2)", borderRadius: "100px", padding: "0.2rem 0.6rem" }}>✓ Verified</span>
                    </div>
                    <div style={{ display: "flex", gap: "0.75rem" }}>
                        <button onClick={() => onContact(prop)} style={{ flex: 1, padding: "0.8rem", background: C.accent, border: "none", borderRadius: "10px", color: "#fff", fontFamily: "inherit", fontSize: "0.85rem", fontWeight: 700, cursor: "pointer" }}>💬 Contact Dealer</button>
                        <button onClick={onClose} style={{ padding: "0.8rem 1.2rem", background: C.surface2, border: `1px solid ${C.border2}`, borderRadius: "10px", color: C.text2, fontFamily: "inherit", fontSize: "0.85rem", cursor: "pointer" }}>Close</button>
                    </div>
                </div>
            </div>
        </div>
    );
}

// ─── BUYER VIEW ──────────────────────────────────────────────────────────────
function BuyerView({ dbProps, onContact, onOpenDetail }) {
    const [search, setSearch] = useState(""); 
    const [typeF, setTypeF] = useState(""); 
    const [cityF, setCityF] = useState(""); 
    const [activeTab, setActiveTab] = useState('all');

    const shown = dbProps.filter(p => { 
        const q = search.toLowerCase(); 
        const matchesSearch = !q || p.title.toLowerCase().includes(q) || p.loc?.toLowerCase().includes(q) || p.location?.toLowerCase().includes(q);
        
        const pType = (p.type || '').toLowerCase();
        const fType = (typeF || '').toLowerCase();
        const matchesType = !fType || pType === fType;

        const pCity = (p.loc || p.location || '').toLowerCase();
        const fCity = (cityF || '').toLowerCase();
        const matchesCity = !fCity || pCity.includes(fCity);

        // Robust status matching (handles 'For Sale' vs 'for-sale')
        const pStatus = (p.status || p.type || '').toLowerCase().replace(/\s+/g, '-');
        const fStatus = activeTab.toLowerCase().replace(/\s+/g, '-');
        const matchesTab = fStatus === 'all' || pStatus.includes(fStatus);
        
        return matchesSearch && matchesType && matchesCity && matchesTab;
    });

    return (
        <div className="properties-section-sync">
            {/* Filter Bar (Mirroring Properties.jsx) */}
            <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '2rem', flexWrap: 'wrap', background: 'var(--surface)', padding: '1.25rem', borderRadius: '16px', border: '1px solid var(--border)' }}>
                <div style={{ flex: 1, minWidth: '240px', position: 'relative' }}>
                    <input 
                        style={{ ...miniInp, marginBottom: 0, paddingLeft: '2.5rem', height: '45px', borderRadius: '10px' }} 
                        value={search} 
                        onChange={e => setSearch(e.target.value)} 
                        placeholder="Search by location, title, or keyword..." 
                    />
                    <span style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', opacity: 0.5 }}>🔍</span>
                </div>
                <select style={{ ...miniSel, marginBottom: 0, width: '140px', height: '45px', borderRadius: '10px' }} value={typeF} onChange={e => setTypeF(e.target.value)}>
                    <option value="">All Types</option>
                    <option value="house">House</option>
                    <option value="apartment">Apartment</option>
                    <option value="villa">Villa</option>
                </select>
                <select style={{ ...miniSel, marginBottom: 0, width: '140px', height: '45px', borderRadius: '10px' }} value={cityF} onChange={e => setCityF(e.target.value)}>
                    <option value="">All Cities</option>
                    <option value="lahore">Lahore</option>
                    <option value="islamabad">Islamabad</option>
                    <option value="karachi">Karachi</option>
                </select>
                <button 
                    onClick={() => { setSearch(''); setTypeF(''); setCityF(''); setActiveTab('all'); }}
                    style={{ padding: '0 1.25rem', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: '10px', color: 'var(--text-2)', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer' }}
                >
                    ✕ Clear
                </button>
            </div>

            {/* Tabs (Mirroring Properties.jsx) */}
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                {['all', 'for-sale', 'for-rent'].map(tab => (
                    <button 
                        key={tab} 
                        onClick={() => setActiveTab(tab)}
                        style={{ 
                            padding: '0.6rem 1.25rem', 
                            background: 'none', 
                            border: 'none', 
                            color: activeTab === tab ? 'var(--accent)' : 'var(--text-3)', 
                            fontWeight: 700, 
                            fontSize: '0.85rem', 
                            cursor: 'pointer',
                            position: 'relative',
                            transition: 'all 0.2s'
                        }}
                    >
                        {tab === 'all' ? 'All Properties' : tab === 'for-sale' ? 'For Sale' : 'For Rent'}
                        {activeTab === tab && <div style={{ position: 'absolute', bottom: '-0.6rem', left: 0, right: 0, height: '3px', background: 'var(--accent)', borderRadius: '10px' }} />}
                    </button>
                ))}
            </div>

            <div style={{ fontSize: "0.75rem", color: C.text3, marginBottom: "1.5rem" }}>
                Showing <span style={{ color: 'var(--text)', fontWeight: 700 }}>{shown.length}</span> properties matching your criteria
            </div>

            {shown.length === 0 ? (
                <div style={{ textAlign: "center", padding: "4rem", background: C.surface, borderRadius: "20px", border: `1px solid ${C.border}` }}>
                    <div style={{ fontSize: "3.5rem", marginBottom: "1rem" }}>🔍</div>
                    <h3 style={{ color: C.text, marginBottom: '0.5rem' }}>No properties found</h3>
                    <p style={{ color: C.text3, fontSize: '0.9rem' }}>Try adjusting your filters or clearing your search.</p>
                </div>
            ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(300px,1fr))", gap: "1.75rem" }}>
                    {shown.map(p => (
                        <div 
                            key={p.id} 
                            style={{ background: 'var(--surface)', borderRadius: '20px', overflow: 'hidden', border: '1px solid var(--border)', cursor: 'pointer', transition: 'all 0.3s ease', display: 'flex', flexDirection: 'column' }}
                            onClick={() => onOpenDetail(p)}
                            onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-8px)'; e.currentTarget.style.boxShadow = '0 20px 40px rgba(0,0,0,0.15)'; }}
                            onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}
                        >
                            <div style={{ height: '220px', position: 'relative', overflow: 'hidden' }}>
                                <img src={p.img} alt={p.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                <span style={{ position: 'absolute', top: '1.25rem', left: '1.25rem', padding: '0.4rem 0.9rem', borderRadius: '100px', fontSize: '0.7rem', fontWeight: 800, textTransform: 'uppercase', background: p.status === 'for-sale' ? 'var(--accent)' : 'var(--green)', color: '#fff', boxShadow: '0 4px 12px rgba(0,0,0,0.2)' }}>
                                    {p.status === 'for-sale' ? 'For Sale' : 'For Rent'}
                                </span>
                            </div>
                            <div style={{ padding: '1.5rem', flex: 1, display: 'flex', flexDirection: 'column' }}>
                                <div style={{ color: 'var(--accent-2)', fontWeight: 800, fontSize: '1.3rem', fontFamily: 'Syne, sans-serif', marginBottom: '0.5rem' }}>
                                    {p.priceLabel}
                                </div>
                                <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text)', marginBottom: '0.4rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                    {p.title}
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-3)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" /><circle cx="12" cy="10" r="3" /></svg>
                                    {p.loc || p.location}
                                </div>
                                
                                <div style={{ display: 'flex', gap: '1rem', padding: '1rem 0', borderTop: '1px solid var(--border)', marginTop: 'auto' }}>
                                    <div style={{ fontSize: '0.82rem', color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: '5px' }}>🛏 {p.beds || 0}</div>
                                    <div style={{ fontSize: '0.82rem', color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: '5px' }}>🚿 {p.baths || 0}</div>
                                    <div style={{ fontSize: '0.82rem', color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: '5px' }}>📐 {p.area}</div>
                                </div>
                                
                                <button 
                                    style={{ marginTop: '1.25rem', width: '100%', padding: '0.85rem', background: 'var(--accent)', border: 'none', borderRadius: '12px', color: '#fff', fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer', boxShadow: '0 4px 15px rgba(59,130,246,0.2)' }}
                                    onClick={e => { e.stopPropagation(); onContact(p); }}
                                >
                                    Contact Dealer
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ─── SELLER INBOX ────────────────────────────────────────────────────────────
function SellerInbox({ currentUser, onOpenChat }) {
    const [convs, setConvs] = useState([]);
    const unsubRef = useRef(null);
    useEffect(() => {
        if (!currentUser) return;
        let alive = true;
        let pollTimer = null;
        const fetchConvs = async () => {
            try {
                // Filter by dealerName == currentUser.name
                const res = await restQuery("conversations", [["dealerName", "==", currentUser.name]], currentUser.idToken);
                if (alive) setConvs(res.sort((a, b) => new Date(b.lastAt) - new Date(a.lastAt)));
            } catch (e) {
                console.error(e);
            }
        };
        fetchConvs();
        pollTimer = setInterval(fetchConvs, 5000);
        return () => { alive = false; clearInterval(pollTimer); };
    }, [currentUser?.name]);
    if (!convs.length) return <div style={{ textAlign: "center", padding: "1.5rem 0", color: C.text3, fontSize: "0.78rem" }}>No enquiries yet.</div>;
    return (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {convs.map(c => {
                const time = c.lastAt?.toDate ? timeAgo(c.lastAt.toDate()) : "";
                return (
                    <div key={c.id} onClick={() => onOpenChat(c)} style={{ display: "flex", alignItems: "center", gap: "0.85rem", padding: "0.75rem", background: C.bg2, border: `1px solid ${C.border}`, borderRadius: "11px", cursor: "pointer" }}>
                        <div style={{ width: 38, height: 38, borderRadius: "50%", background: "linear-gradient(135deg,#3b82f6,#8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, color: "#fff", fontSize: "0.8rem", flexShrink: 0 }}>{initials(c.buyerName || "B")}</div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: "0.82rem", fontWeight: 600, color: C.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.buyerName || "Buyer"}</div>
                            <div style={{ fontSize: "0.72rem", color: C.text3, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.lastMessage || "Started a conversation"}</div>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "0.3rem", flexShrink: 0 }}>
                            <span style={{ fontSize: "0.65rem", color: C.text3 }}>{time}</span>
                            {c.unreadDealer > 0 && <span style={{ width: 18, height: 18, borderRadius: "50%", background: C.accent, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.62rem", fontWeight: 700, color: "#fff" }}>{c.unreadDealer}</span>}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

// ─── SELLER VIEW ─────────────────────────────────────────────────────────────
function SellerView({ currentUser, dbProps, onAddListing, onOpenSellerChat }) {
    const [form, setForm] = useState({ title: "", price: "", type: "For Sale", loc: "", area: "", beds: "", bath: "", desc: "", mapUrl: "", mapImage: "" });
    const [imgName, setImgName] = useState(null);
    const setF = (k, v) => setForm(f => ({ ...f, [k]: v }));
    const handleUpload = () => {
        if (!form.title || !form.price || !form.loc) { alert("Please fill Title, Price and Location."); return; }
        onAddListing({ emoji: "🏠", title: form.title, price: "₨ " + form.price, loc: form.loc, type: form.type.includes("Rent") ? "rent" : "sale", tags: [form.area, form.beds ? form.beds + " Beds" : "", form.bath ? form.bath + " Bath" : ""].filter(Boolean), desc: form.desc || "Listed by " + currentUser.name, dealer: currentUser.name, dealerUid: currentUser.uid, dealerGrad: "linear-gradient(135deg,#3b82f6,#8b5cf6)", dealerTag: "Private Seller", mapUrl: form.mapUrl, mapImage: form.mapImage });
        setForm({ title: "", price: "", type: "For Sale", loc: "", area: "", beds: "", bath: "", desc: "", mapUrl: "", mapImage: "" }); setImgName(null);
    };
    const Bdg = ({ label, color, border }) => <span style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", padding: "0.2rem 0.6rem", borderRadius: "100px", background: color, color: "#fff", border: `1px solid ${border}` }}>{label}</span>;
    const myListings = dbProps.filter(p => p.dealerUid === currentUser.uid);
    return (
        <div>
            <div style={{ fontWeight: 700, fontSize: "1rem", color: C.text, marginBottom: "1rem" }}>Seller Dashboard</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(320px,1fr))", gap: "1.5rem", marginBottom: "2rem" }}>
                <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: "16px", overflow: "hidden" }}>
                    <div style={{ padding: "1.25rem 1.5rem", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <span style={{ fontWeight: 700, fontSize: "0.9rem", color: C.text }}>Upload New Property</span>
                        <Bdg label="New Listing" color="rgba(16,185,129,0.18)" border="rgba(16,185,129,0.3)" />
                    </div>
                    <div style={{ padding: "1.25rem 1.5rem" }}>
                        <label style={{ display: "block", border: `2px dashed ${C.border2}`, borderRadius: "12px", padding: "1.5rem 1rem", textAlign: "center", cursor: "pointer", background: C.bg2, marginBottom: "1rem" }}>
                            <input type="file" accept="image/*" style={{ display: "none" }} onChange={e => setImgName(e.target.files[0]?.name || null)} />
                            <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>{imgName ? "✅" : "📸"}</div>
                            <div style={{ fontSize: "0.8rem", color: C.text2 }}>{imgName || "Click to upload property photos"}</div>
                            <div style={{ fontSize: "0.7rem", color: C.text3 }}>JPG, PNG — up to 10MB</div>
                        </label>
                        <input style={miniInp} placeholder="Property Title" value={form.title} onChange={e => setF("title", e.target.value)} />
                        
                        {/* NEW: DEDICATED MAP SECTION */}
                        <div style={{ padding: '1rem', background: 'rgba(59, 130, 246, 0.05)', borderRadius: '12px', border: '1px dashed var(--accent)', marginBottom: '1rem' }}>
                            <div style={{ fontSize: '0.65rem', fontWeight: 800, color: 'var(--accent)', marginBottom: '0.5rem', textTransform: 'uppercase' }}>📍 Dedicated Location Section</div>
                            <input 
                                style={{ ...miniInp, border: '1px solid var(--accent)', marginBottom: '0.5rem' }} 
                                placeholder="Google Maps URL (Required)" 
                                value={form.mapUrl} 
                                onChange={e => setF("mapUrl", e.target.value)} 
                            />
                            <input 
                                style={{ ...miniInp, marginBottom: 0 }} 
                                placeholder="Map Area Image URL (Optional)" 
                                value={form.mapImage} 
                                onChange={e => setF("mapImage", e.target.value)} 
                            />
                        </div>

                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem" }}>
                            <input style={miniInp} placeholder="Price (₨)" value={form.price} onChange={e => setF("price", e.target.value)} />
                            <select style={miniSel} value={form.type} onChange={e => setF("type", e.target.value)}><option>For Sale</option><option>For Rent</option><option>Commercial</option></select>
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem" }}>
                            <input style={miniInp} placeholder="Location / City" value={form.loc} onChange={e => setF("loc", e.target.value)} />
                            <input style={miniInp} placeholder="Area (Marla/Kanal)" value={form.area} onChange={e => setF("area", e.target.value)} />
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem" }}>
                            <input style={miniInp} placeholder="Bedrooms" value={form.beds} onChange={e => setF("beds", e.target.value)} />
                            <input style={miniInp} placeholder="Bathrooms" value={form.bath} onChange={e => setF("bath", e.target.value)} />
                        </div>
                        <input style={miniInp} placeholder="Brief description…" value={form.desc} onChange={e => setF("desc", e.target.value)} />
                        <button onClick={handleUpload} style={{ width: "100%", padding: "0.75rem", background: C.green, border: "none", borderRadius: "9px", color: "#fff", fontFamily: "inherit", fontSize: "0.83rem", fontWeight: 700, cursor: "pointer", boxShadow: "0 4px 16px rgba(16,185,129,0.3)" }}>🚀 Publish Listing</button>
                    </div>
                </div>
                <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: "16px", overflow: "hidden" }}>
                    <div style={{ padding: "1.25rem 1.5rem", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <span style={{ fontWeight: 700, fontSize: "0.9rem", color: C.text }}>My Active Listings</span>
                        <Bdg label={myListings.length + " Live"} color="rgba(59,130,246,0.18)" border="rgba(59,130,246,0.3)" />
                    </div>
                    <div style={{ padding: "1.25rem 1.5rem" }}>
                        {myListings.length === 0
                            ? <div style={{ textAlign: "center", padding: "2rem 0", color: C.text3, fontSize: "0.8rem" }}>No listings yet.<br />Upload your first property above.</div>
                            : <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                                {myListings.map(p => (
                                    <div key={p.id} style={{ display: "flex", alignItems: "center", gap: "0.85rem", padding: "0.75rem", background: C.bg2, border: `1px solid ${C.border}`, borderRadius: "11px" }}>
                                        <div style={{ width: 42, height: 42, borderRadius: "8px", background: "linear-gradient(135deg,#1a2a4a,#0f1a2e)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.2rem", flexShrink: 0 }}>{p.emoji}</div>
                                        <div style={{ flex: 1, minWidth: 0 }}>
                                            <div style={{ fontSize: "0.8rem", fontWeight: 600, color: C.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.title}</div>
                                            <div style={{ fontSize: "0.68rem", color: C.text3 }}>{p.price} · {p.loc}</div>
                                        </div>
                                        <span style={{ fontSize: "0.65rem", fontWeight: 700, padding: "0.2rem 0.55rem", borderRadius: "100px", background: "rgba(16,185,129,0.12)", color: "#34d399", border: "1px solid rgba(16,185,129,0.2)" }}>Live</span>
                                    </div>
                                ))}
                            </div>
                        }
                    </div>
                </div>
            </div>
            <div style={{ fontWeight: 700, fontSize: "1rem", color: C.text, marginBottom: "1rem" }}>Buyer Enquiries</div>
            <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: "16px", overflow: "hidden" }}>
                <div style={{ padding: "1.25rem 1.5rem", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span style={{ fontWeight: 700, fontSize: "0.9rem", color: C.text }}>Messages from Buyers</span>
                    <Bdg label="Live" color="rgba(16,185,129,0.18)" border="rgba(16,185,129,0.3)" />
                </div>
                <div style={{ padding: "1.25rem 1.5rem" }}>
                    <SellerInbox currentUser={currentUser} onOpenChat={onOpenSellerChat} />
                </div>
            </div>
        </div>
    );
}

// ─── HOME PAGE ────────────────────────────────────────────────────────────────
function HomePage({ onEnter }) {
    return (
        <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: "'Segoe UI',sans-serif", display: "flex", flexDirection: "column" }}>
            <nav style={{ height: "64px", display: "flex", alignItems: "center", padding: "0 2.5rem", borderBottom: `1px solid ${C.border}`, justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "2.5rem" }}>
                    <Link to="/" style={{ textDecoration: "none" }}><span style={{ fontWeight: 800, fontSize: "1.3rem", color: C.text, letterSpacing: "-0.03em" }}>Housing<span style={{ color: C.accent }}>.</span>AI</span></Link>
                    <div style={{ display: "flex", gap: "1.5rem" }}>
                        {[["2D Design", "/2d-design"], ["3D Design", "/3d-design"], ["Cost Estimation", "/cost-estimation"], ["Interior Design", "/interior-design"], ["Properties", "/properties"]].map(([lbl, url]) => (
                            <Link key={url} to={url} style={{ fontSize: "0.83rem", fontWeight: 500, color: C.text3, textDecoration: "none", transition: "all 0.2s" }} onMouseOver={e => e.target.style.color = C.text2} onMouseOut={e => e.target.style.color = C.text3}>{lbl}</Link>
                        ))}
                    </div>
                </div>
                <div style={{ display: "flex", gap: "0.75rem" }}>
                    <button onClick={() => onEnter("login")} style={{ padding: "0.5rem 1.2rem", background: "none", border: `1px solid ${C.border2}`, borderRadius: "9px", color: C.text2, fontFamily: "inherit", fontSize: "0.83rem", fontWeight: 600, cursor: "pointer" }}>Sign In</button>
                    <button onClick={() => onEnter("signup")} style={{ padding: "0.5rem 1.2rem", background: C.accent, border: "none", borderRadius: "9px", color: "#fff", fontFamily: "inherit", fontSize: "0.83rem", fontWeight: 700, cursor: "pointer", boxShadow: "0 4px 16px rgba(59,130,246,0.35)" }}>Get Started</button>
                </div>
            </nav>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "4rem 2rem", textAlign: "center", position: "relative", overflow: "hidden" }}>
                <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse 80% 60% at 50% 0%,rgba(59,130,246,0.10),transparent 70%)", pointerEvents: "none" }} />
                <div style={{ fontSize: "0.78rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: C.accent, marginBottom: "1.25rem", background: "rgba(59,130,246,0.10)", border: `1px solid rgba(59,130,246,0.2)`, borderRadius: "100px", padding: "0.35rem 1rem" }}>Pakistan's #1 AI Property Platform</div>
                <h1 style={{ fontWeight: 800, fontSize: "3.2rem", color: C.text, lineHeight: 1.1, letterSpacing: "-0.04em", marginBottom: "1.25rem", maxWidth: "720px" }}>Find, Design &{" "}<span style={{ color: C.accent }}>Own</span> your dream home.</h1>
                <p style={{ fontSize: "1rem", color: C.text2, lineHeight: 1.7, maxWidth: "520px", marginBottom: "2.5rem" }}>Discover properties, chat with verified dealers, generate AI floor plans, and estimate construction costs — all in one place.</p>
                <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", justifyContent: "center" }}>
                    <button onClick={() => onEnter("signup")} style={{ padding: "0.9rem 2rem", background: C.accent, border: "none", borderRadius: "12px", color: "#fff", fontFamily: "inherit", fontSize: "0.95rem", fontWeight: 700, cursor: "pointer", boxShadow: "0 8px 32px rgba(59,130,246,0.4)" }}>Start for Free →</button>
                    <button onClick={() => onEnter("login")} style={{ padding: "0.9rem 2rem", background: C.surface, border: `1px solid ${C.border2}`, borderRadius: "12px", color: C.text2, fontFamily: "inherit", fontSize: "0.95rem", fontWeight: 600, cursor: "pointer" }}>Sign In</button>
                </div>
            </div>
            <div style={{ display: "flex", justifyContent: "center", gap: "3rem", padding: "2rem", borderTop: `1px solid ${C.border}`, flexWrap: "wrap" }}>
                {[["12K+", "Properties Listed"], ["4.2K", "Verified Dealers"], ["98%", "Satisfied Users"], ["3D", "AI Design Tools"]].map(([v, l]) => (
                    <div key={l} style={{ textAlign: "center" }}>
                        <div style={{ fontWeight: 800, fontSize: "1.6rem", color: C.text }}>{v}</div>
                        <div style={{ fontSize: "0.72rem", color: C.text3, marginTop: "0.2rem" }}>{l}</div>
                    </div>
                ))}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(220px,1fr))", gap: "1rem", padding: "2rem 2.5rem 3rem", maxWidth: "1200px", margin: "0 auto", width: "100%" }}>
                {[{ icon: "🏠", title: "Browse Properties", desc: "Search thousands of listings filtered by city, budget and type." }, { icon: "💬", title: "Chat with Dealers", desc: "Real-time messaging with verified property dealers." }, { icon: "🤖", title: "AI Floor Plans", desc: "Generate 2D & 3D designs from a simple text prompt." }, { icon: "📊", title: "Cost Estimation", desc: "Get accurate construction cost breakdowns instantly." }].map(f => (
                    <div key={f.title} style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: "16px", padding: "1.5rem", cursor: "pointer" }} onClick={() => onEnter("signup")}>
                        <div style={{ fontSize: "2rem", marginBottom: "0.75rem" }}>{f.icon}</div>
                        <div style={{ fontWeight: 700, fontSize: "0.9rem", color: C.text, marginBottom: "0.4rem" }}>{f.title}</div>
                        <div style={{ fontSize: "0.78rem", color: C.text2, lineHeight: 1.6 }}>{f.desc}</div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ─── AUTH SCREEN ─────────────────────────────────────────────────────────────
function AuthScreen({ defaultTab = "login", onGoHome }) {
    const navigate = useNavigate();
    const [tab, setTab] = useState(defaultTab);
    useEffect(() => { setTab(defaultTab); }, [defaultTab]);
    const [role, setRole] = useState("buyer");
    const [form, setForm] = useState({ email: "", password: "", name: "", cnic: "", mobile: "" });
    const [errs, setErrs] = useState({});
    const [formErr, setFormErr] = useState("");
    const [loading, setLoading] = useState(false);

    // ── Single stable onChange handler — NO inline function components ──
    const handleChange = useCallback((key, value) => {
        setForm(f => ({ ...f, [key]: value }));
        setErrs(e => ({ ...e, [key]: "" }));
    }, []);

    const validate = () => {
        const e = {};
        if (tab === "signup") {
            if (!form.name || form.name.length < 3) e.name = "Enter your full name.";
            if (!/^\d{5}-\d{7}-\d$/.test(form.cnic)) e.cnic = "Enter valid CNIC (XXXXX-XXXXXXX-X).";
            if (!/^0\d{3}-\d{7}$/.test(form.mobile)) e.mobile = "Enter valid Pakistan mobile number.";
        }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = "Enter a valid email address.";
        if (form.password.length < 6) e.password = "Password must be at least 6 characters.";
        setErrs(e); return Object.keys(e).length === 0;
    };

    const handleAuth = async () => {
        if (!validate()) return;
        setLoading(true); setFormErr("");
        try {
            if (tab === "login") {
                const res = await restLogin(form.email, form.password);
                const userDoc = await restGetDoc("users", res.localId, res.idToken);
                const role = userDoc?.role || "buyer";
                const userData = { uid: res.localId, email: form.email, name: userDoc?.name || res.displayName || "User", role, idToken: res.idToken };
                localStorage.setItem("housing_user", JSON.stringify(userData));
                window.location.reload(); // Refresh to trigger App's user detection
            } else {
                const res = await restSignup(form.email, form.password);
                await restUpdateProfile(res.idToken, form.name);
                const userData = { uid: res.localId, email: form.email, name: form.name, role, idToken: res.idToken };
                await restSetDoc("users", res.localId, { name: form.name, cnic: form.cnic, mobile: form.mobile, email: form.email, role, createdAt: new Date().toISOString() }, res.idToken);
                localStorage.setItem("housing_user", JSON.stringify(userData));
                window.location.reload();
            }
        } catch (e) {
            const m = { "EMAIL_NOT_FOUND": "No account found. Please sign up.", "INVALID_PASSWORD": "Incorrect password.", "EMAIL_EXISTS": "Email already in use.", "WEAK_PASSWORD": "Password too weak (min 6 chars)." };
            setFormErr(m[e.message] || e.message); setLoading(false);
        }
    };

    return (
        <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: "'Segoe UI',sans-serif", display: "grid", gridTemplateColumns: "1fr 1fr" }}>
            {/* Visual panel */}
            <div style={{ position: "relative", background: C.bg2, borderRight: `1px solid ${C.border}`, display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "3rem", overflow: "hidden" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <Link to="/" style={{ textDecoration: "none" }}><span style={{ fontWeight: 800, fontSize: "1.5rem", color: C.text, letterSpacing: "-0.03em" }}>Housing<span style={{ color: C.accent }}>.</span>AI</span></Link>
                    <div style={{ display: "flex", gap: "1rem" }}>
                        {[["2D", "/2d-design"], ["3D", "/3d-design"], ["Cost", "/cost-estimation"], ["Interior", "/interior-design"], ["Props", "/properties"]].map(([lbl, url]) => (
                            <Link key={url} to={url} style={{ fontSize: "0.72rem", fontWeight: 600, color: C.text3, textDecoration: "none" }}>{lbl}</Link>
                        ))}
                    </div>
                </div>
                <div>
                    <h1 style={{ fontWeight: 800, fontSize: "2.2rem", color: C.text, lineHeight: 1.15, letterSpacing: "-0.03em", marginBottom: "0.75rem" }}>Find, Design &<br /><em style={{ fontStyle: "normal", color: C.accent }}>Own</em> your dream<br />home.</h1>
                    <p style={{ fontSize: "0.88rem", color: C.text2, lineHeight: 1.7, maxWidth: "320px" }}>Join thousands of Pakistanis using Housing.AI to discover properties, connect with dealers, and visualize their future home in 3D.</p>
                </div>
                <div style={{ display: "flex", gap: "2rem" }}>
                    {[["12K+", "Properties Listed"], ["4.2K", "Active Dealers"], ["98%", "Satisfied Users"]].map(([v, l]) => (
                        <div key={l}><div style={{ fontWeight: 800, fontSize: "1.4rem", color: C.text }}>{v}</div><div style={{ fontSize: "0.72rem", color: C.text3, marginTop: "0.1rem" }}>{l}</div></div>
                    ))}
                </div>
            </div>

            {/* Form panel */}
            <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "3rem 2rem", background: C.bg, overflowY: "auto", position: "relative" }}>
                {/* ✕ Back to Home */}
                <button onClick={onGoHome} title="Back to Home" style={{ position: "absolute", top: "1.25rem", right: "1.25rem", width: 36, height: 36, borderRadius: "50%", background: C.surface, border: `1px solid ${C.border2}`, color: C.text2, fontSize: "1rem", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "inherit" }}>✕</button>

                <div style={{ width: "100%", maxWidth: "420px" }}>
                    {/* Tabs */}
                    <div style={{ display: "flex", background: C.surface, border: `1px solid ${C.border2}`, borderRadius: "14px", padding: "4px", marginBottom: "2rem", gap: "4px" }}>
                        {["login", "signup"].map(t => (
                            <button key={t} onClick={() => { setTab(t); setFormErr(""); setErrs({}); }} style={{ flex: 1, textAlign: "center", padding: "0.7rem", borderRadius: "10px", fontWeight: 600, cursor: "pointer", border: "none", fontSize: "0.85rem", transition: "all 0.22s", background: tab === t ? C.accent : "none", color: tab === t ? "#fff" : C.text3, fontFamily: "inherit" }}>
                                {t === "login" ? "Sign In" : "Create Account"}
                            </button>
                        ))}
                    </div>

                    <div style={{ fontWeight: 800, fontSize: "1.6rem", color: C.text, letterSpacing: "-0.03em", marginBottom: "0.35rem" }}>{tab === "login" ? "Welcome back" : "Create account"}</div>
                    <div style={{ fontSize: "0.82rem", color: C.text2, marginBottom: "1.5rem" }}>{tab === "login" ? "Sign in to your Housing.AI account." : "Join Housing.AI — it's free to get started."}</div>

                    {/* Role selector (signup only) */}
                    {tab === "signup" && (
                        <div style={{ marginBottom: "1rem" }}>
                            <label style={{ display: "block", fontSize: "0.72rem", fontWeight: 600, color: C.text2, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: "0.5rem" }}>I want to</label>
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem", marginBottom: "0.5rem" }}>
                                {[["buyer", "🏠", "Buy / Rent", "Browse properties"], ["seller", "🏢", "Sell / List", "Upload properties"]].map(([r, ic, lb, sb]) => (
                                    <div key={r} onClick={() => setRole(r)} style={{ background: role === r ? "rgba(59,130,246,0.08)" : C.surface, border: `1px solid ${role === r ? C.accent : C.border2}`, borderRadius: "11px", padding: "0.8rem 0.6rem", cursor: "pointer", textAlign: "center", color: C.text }}>
                                        <div style={{ fontSize: "1.4rem", marginBottom: "0.3rem" }}>{ic}</div>
                                        <div style={{ fontSize: "0.74rem", fontWeight: 600, color: C.text2 }}>{lb}</div>
                                        <div style={{ fontSize: "0.64rem", color: C.text3 }}>{sb}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {formErr && <div style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: "10px", padding: "0.7rem 0.9rem", fontSize: "0.78rem", color: "#fca5a5", marginBottom: "1rem" }}>{formErr}</div>}

                    {/* Fields — using the stable AuthField component defined outside */}
                    {tab === "signup" && <>
                        <AuthField fieldKey="name" label="Full Name" value={form.name} error={errs.name} onChange={handleChange} onSubmit={handleAuth} />
                        <AuthField fieldKey="cnic" label="CNIC" value={form.cnic} error={errs.cnic} onChange={handleChange} onSubmit={handleAuth} transform={fmtCNIC} />
                        <AuthField fieldKey="mobile" label="Mobile Number" value={form.mobile} error={errs.mobile} onChange={handleChange} onSubmit={handleAuth} transform={fmtMobile} />
                    </>}
                    <AuthField fieldKey="email" label="Email Address" value={form.email} error={errs.email} onChange={handleChange} onSubmit={handleAuth} type="email" />
                    <AuthField fieldKey="password" label="Password" value={form.password} error={errs.password} onChange={handleChange} onSubmit={handleAuth} type="password" showStrength={tab === "signup"} />

                    <button onClick={handleAuth} disabled={loading} style={{ width: "100%", padding: "0.9rem", background: C.accent, border: "none", borderRadius: "12px", color: "#fff", fontFamily: "inherit", fontSize: "0.92rem", fontWeight: 700, cursor: "pointer", boxShadow: "0 6px 28px rgba(59,130,246,0.35)", opacity: loading ? 0.7 : 1, marginTop: "0.25rem" }}>
                        {loading ? "Processing…" : tab === "login" ? "Sign In →" : "Create My Account →"}
                    </button>
                    <p style={{ fontSize: "0.72rem", color: C.text3, marginTop: "1rem", textAlign: "center" }}>
                        {tab === "login" ? "Don't have an account? " : "Already have an account? "}
                        <span style={{ color: C.accent2, cursor: "pointer" }} onClick={() => { setTab(tab === "login" ? "signup" : "login"); setFormErr(""); setErrs({}); }}>
                            {tab === "login" ? "Create one free" : "Sign in"}
                        </span>
                    </p>
                </div>
            </div>
        </div>
    );
}

// ─── DASHBOARD ───────────────────────────────────────────────────────────────
function Dashboard({ user, onLogout }) {
    const [view, setView] = useState(user?.role || "buyer");
    const [dbProps, setDbProps] = useState([]);
    const [chat, setChat] = useState(null);
    const [toast, setToast] = useState(null);
    const timerRef = useRef(null);

    useEffect(() => {
        let isM = true;
        // Fetch all properties to ensure consistency with the main Properties page
        restQuery("properties", []).then(res => { 
            if (isM && res) {
                // NORMALIZE the data exactly like Properties.jsx does
                const normalized = res.map(data => {
                    const status = data.type === 'For Sale' ? 'for-sale'
                        : data.type === 'For Rent' ? 'for-rent'
                            : (data.status || 'for-sale');

                    const propertyType = (data.propertyType || data.category || 'house').toLowerCase();
                    const priceVal = typeof data.price === 'number' ? data.price : parseFloat(data.price) || 0;

                    return {
                        ...data,
                        status: status,
                        type: data.type || 'sale', // keeping original for the 'all' filter
                        price: priceVal,
                        priceLabel: data.priceLabel || (status === 'for-rent' 
                            ? `RS ${priceVal.toLocaleString()}/mo` 
                            : `RS ${priceVal.toLocaleString()}`),
                        img: data.image || data.img || 'https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800&q=80',
                        tags: data.tags || [data.area, data.beds ? `${data.beds} Beds` : ""].filter(Boolean),
                        dealer: data.dealerName || data.dealer || 'Property Owner'
                    };
                });
                setDbProps(normalized); 
            }
        }).catch(err => {
            console.error("Dashboard Fetch Error:", err);
        });
        return () => { isM = false; };
    }, []);

    const showToast = useCallback((title, sub, icon = "✅") => { clearTimeout(timerRef.current); setToast({ title, sub, icon }); timerRef.current = setTimeout(() => setToast(null), 4000); }, []);
    const openContact = useCallback(prop => { const convId = buildConvId(user.uid, prop.dealerUid || prop.dealer, "Re: " + prop.title); setChat({ convId, headerName: prop.dealer, headerGrad: prop.dealerGrad || C.accent, headerProp: "Re: " + prop.title }); }, [user.uid]);
    const openSellerChat = useCallback(async conv => {
        const convId = conv.id;
        setChat({ convId, headerName: conv.buyerName || "Buyer", headerGrad: "linear-gradient(135deg,#3b82f6,#8b5cf6)", headerProp: conv.propertyTitle });
        try { await restSetDoc("conversations", convId, { unreadDealer: 0 }, user.idToken); } catch (_) { }
    }, [user.idToken]);
    const addListing = useCallback(async p => { 
        setDbProps(l => [...l, p]); 
        showToast("🚀 Property Listed!", "Your listing is now live."); 
        try { await restAddDoc("properties", p, user.idToken); } catch (e) { console.error(e); } 
    }, [showToast, user.idToken]);

    const isBuyer = view === "buyer";
    return (
        <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: "'Segoe UI',sans-serif", display: "flex", flexDirection: "column" }}>
            <nav style={{ position: "sticky", top: 0, zIndex: 100, height: "62px", display: "flex", alignItems: "center", padding: "0 2rem", background: "rgba(7,9,14,0.95)", backdropFilter: "blur(20px)", borderBottom: `1px solid ${C.border}` }}>
                {/* Logo - Left */}
                <div style={{ flex: 1 }}>
                    <Link to="/" style={{ textDecoration: "none" }}><span style={{ fontWeight: 800, fontSize: "1.2rem", color: C.text, letterSpacing: "-0.03em" }}>Housing<span style={{ color: C.accent }}>.</span>AI</span></Link>
                </div>
                
                {/* Navigation - Center */}
                <div style={{ display: "flex", gap: "2rem", alignItems: "center", justifyContent: "center" }}>
                    {["buyer", "seller"].map(v => (
                        <button key={v} onClick={() => setView(v)} style={{ fontSize: "0.9rem", fontWeight: 600, color: view === v ? C.text : C.text3, cursor: "pointer", background: "none", border: "none", fontFamily: "inherit", transition: "color 0.2s" }}>
                            {v === "buyer" ? "Browse Properties" : "My Listings"}
                        </button>
                    ))}
                </div>
                
                {/* User Settings - Right */}
                <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "1rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 4, background: C.surface2, border: `1px solid ${C.border2}`, borderRadius: "100px", padding: "0.25rem 0.35rem" }}>
                        {["buyer", "seller"].map(r => (
                            <button key={r} onClick={() => setView(r)} style={{ padding: "0.25rem 0.7rem", borderRadius: "100px", fontSize: "0.72rem", fontWeight: 600, cursor: "pointer", border: "none", fontFamily: "inherit", background: view === r ? C.accent : "none", color: view === r ? "#fff" : C.text3, transition: "all 0.2s" }}>
                                {r === "buyer" ? "🏠 Buyer" : "🏢 Seller"}
                            </button>
                        ))}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", background: C.surface, border: `1px solid ${C.border2}`, borderRadius: "100px", padding: "0.3rem 0.9rem 0.3rem 0.4rem" }}>
                        <div style={{ width: 28, height: 28, borderRadius: "50%", background: "linear-gradient(135deg,#3b82f6,#8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.7rem", fontWeight: 700, color: "#fff" }}>{initials(user.name)}</div>
                        <span style={{ fontSize: "0.78rem", fontWeight: 600, color: C.text }}>{user.name}</span>
                    </div>
                    <button onClick={onLogout} style={{ background: "none", border: `1px solid ${C.border2}`, borderRadius: "8px", padding: "0.35rem 0.8rem", color: C.text3, fontFamily: "inherit", fontSize: "0.76rem", cursor: "pointer" }}>Logout</button>
                </div>
            </nav>
            <div style={{ padding: "2rem", maxWidth: "1200px", margin: "0 auto", width: "100%" }}>
                <div style={{ background: "linear-gradient(135deg,#111521,#181d2e)", border: `1px solid ${C.border2}`, borderRadius: "20px", padding: "2rem 2.5rem", marginBottom: "2rem", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1.5rem" }}>
                    <div>
                        <div style={{ fontSize: "0.8rem", color: C.text3, fontWeight: 500, marginBottom: "0.3rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>Welcome back 👋</div>
                        <div style={{ fontWeight: 800, fontSize: "1.7rem", color: C.text, letterSpacing: "-0.03em", marginBottom: "0.4rem" }}>Hello, <span style={{ color: C.accent2 }}>{user.name.split(" ")[0]}</span>!</div>
                        <div style={{ fontSize: "0.83rem", color: C.text2 }}>{isBuyer ? "Browse properties and contact dealers directly." : "Upload your properties and manage buyer enquiries."}</div>
                    </div>
                    <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                        <div style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)', borderRadius: '12px', padding: '0.75rem 1rem', textAlign: 'center' }}>
                            <div style={{ fontWeight: 800, fontSize: "1.2rem", color: C.accent2 }}>{dbProps.length}</div>
                            <div style={{ fontSize: "0.6rem", color: C.text3, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total in DB</div>
                        </div>
                        <div style={{ background: isBuyer ? "rgba(59,130,246,0.1)" : "rgba(16,185,129,0.1)", border: `1px solid ${isBuyer ? "rgba(59,130,246,0.25)" : "rgba(16,185,129,0.25)"}`, borderRadius: "12px", padding: "1rem 1.25rem", textAlign: "center", flexShrink: 0 }}>
                            <div style={{ fontWeight: 800, fontSize: "1.4rem", color: isBuyer ? C.accent2 : "#34d399" }}>{isBuyer ? "Buyer" : "Seller"}</div>
                            <div style={{ fontSize: "0.68rem", color: C.text3, marginTop: "0.1rem" }}>Account Mode</div>
                        </div>
                    </div>
                </div>
                {isBuyer
                    ? <BuyerView dbProps={dbProps} onContact={openContact} />
                    : <SellerView currentUser={user} dbProps={dbProps} onAddListing={addListing} onOpenSellerChat={openSellerChat} />
                }
            </div>
            {chat && <ChatModal {...chat} currentUser={user} onClose={() => setChat(null)} />}
            <Toast t={toast} />
        </div>
    );
}

// ─── ROOT ────────────────────────────────────────────────────────────────────
export default function App() {
    const [user, setUser] = useState(null);
    const [checking, setChecking] = useState(true);
    const [screen, setScreen] = useState("home"); // "home" | "login" | "signup"
    const loc = useLocation();
    const nav = useNavigate();

    useEffect(() => {
        const params = new URLSearchParams(loc.search);
        const t = params.get("tab");
        if (t === "login" || t === "signup") setScreen(t);
    }, [loc.search]);

    useEffect(() => {
        const saved = localStorage.getItem("housing_user");
        if (saved) {
            try {
                const u = JSON.parse(saved);
                setUser(u);
                setScreen("home");
            } catch (e) { localStorage.removeItem("housing_user"); }
        }
        setChecking(false);
    }, []);

    const handleLogout = () => { localStorage.removeItem("housing_user"); setUser(null); navigate("/"); window.location.reload(); };

    if (checking) return (
        <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: "1rem", fontFamily: "'Segoe UI',sans-serif" }}>
            <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
            <div style={{ width: 40, height: 40, border: `3px solid ${C.border2}`, borderTopColor: C.accent, borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
            <span style={{ color: C.text3, fontSize: "0.85rem" }}>Loading Housing.AI…</span>
        </div>
    );

    // ── user check is ALWAYS first — auth state wins over screen state ──
    if (user) return <Dashboard user={user} onLogout={handleLogout} />;
    if (screen === "home") return <HomePage onEnter={tab => setScreen(tab)} />;
    return <AuthScreen defaultTab={screen} onGoHome={() => nav("/")} />;
}