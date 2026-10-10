import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { authErrorMessage, useAuth } from "../auth/AuthContext";
import api from "../api";

// ─── HELPERS ─────────────────────────────────────────────────────────────────
const fmtCNIC = v => { let d = v.replace(/\D/g, ""); if (d.length > 5) d = d.slice(0, 5) + "-" + d.slice(5); if (d.length > 13) d = d.slice(0, 13) + "-" + d.slice(13, 14); return d; };
const fmtMobile = v => { let d = v.replace(/\D/g, ""); if (d.length > 4) d = d.slice(0, 4) + "-" + d.slice(4, 11); return d; };

/** Only same-site paths are accepted as a post-login destination. */
const safeNext = (next) => (next && next.startsWith("/") && !next.startsWith("//") ? next : null);

// ─── DESIGN TOKENS ───────────────────────────────────────────────────────────
const C = { bg: "#07090e", bg2: "#0c0f18", surface: "#111521", border: "rgba(255,255,255,0.06)", border2: "rgba(255,255,255,0.10)", text: "#eef0f8", text2: "#8892aa", text3: "#454e64", accent: "#3b82f6", accent2: "#60a5fa" };

const inpStyle = (hasErr = false) => ({ width: "100%", background: C.surface, border: `1px solid ${hasErr ? "#ef4444" : C.border2}`, borderRadius: "11px", padding: "0.75rem 0.9rem", color: C.text, fontFamily: "inherit", fontSize: "0.88rem", outline: "none", boxSizing: "border-box" });

// ─── AUTH FIELD — defined at module level to prevent remount on each render ──
function AuthField({ label, fieldKey, type = "text", value, error, onChange, onSubmit, transform, showStrength }) {
    let s = 0;
    if (showStrength && value) { if (value.length >= 8) s++; if (/[A-Z]/.test(value)) s++; if (/[0-9]/.test(value)) s++; if (/[^A-Za-z0-9]/.test(value)) s++; }
    const strengthCols = ["", "#ef4444", "#f59e0b", "#3b82f6", "#10b981"];
    const strengthLabs = ["", "Weak", "Fair", "Good", "Strong"];
    const id = `auth-${fieldKey}`;
    return (
        <div style={{ marginBottom: "0.9rem" }}>
            <label htmlFor={id} style={{ display: "block", fontSize: "0.72rem", fontWeight: 600, color: C.text2, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: "0.4rem" }}>{label}</label>
            <input
                id={id}
                type={type}
                value={value}
                placeholder={label}
                autoComplete={type === "password" ? (showStrength ? "new-password" : "current-password") : fieldKey}
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

// ─── FORGOT PASSWORD: email → 6-digit code → new password ────────────────────
const RESEND_SECONDS = 60;
const btnStyle = (busy) => ({ width: "100%", padding: "0.9rem", background: C.accent, border: "none", borderRadius: "12px", color: "#fff", fontFamily: "inherit", fontSize: "0.92rem", fontWeight: 700, cursor: "pointer", boxShadow: "0 6px 28px rgba(59,130,246,0.35)", opacity: busy ? 0.7 : 1, marginTop: "0.25rem" });
const linkBtn = { color: C.accent2, cursor: "pointer", background: "none", border: "none", padding: 0, font: "inherit" };

function ForgotPassword({ initialEmail, onBack, onDone }) {
    const [step, setStep] = useState("email");   // email | code | password
    const [form, setForm] = useState({ email: initialEmail || "", code: "", password: "", confirm: "" });
    const [errs, setErrs] = useState({});
    const [formErr, setFormErr] = useState("");
    const [info, setInfo] = useState("");
    const [busy, setBusy] = useState(false);
    const [token, setToken] = useState("");
    const [wait, setWait] = useState(0);

    useEffect(() => {
        if (wait <= 0) return undefined;
        const t = setTimeout(() => setWait(w => w - 1), 1000);
        return () => clearTimeout(t);
    }, [wait]);

    const handleChange = useCallback((key, value) => {
        setForm(f => ({ ...f, [key]: value }));
        setErrs(e => ({ ...e, [key]: "" }));
    }, []);

    const run = async (fn) => {
        if (busy) return;
        setBusy(true); setFormErr("");
        try { await fn(); } catch (e) { setFormErr(e.message || "Something went wrong. Please try again."); }
        finally { setBusy(false); }
    };

    const sendCode = () => {
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) { setErrs({ email: "Enter a valid email address." }); return; }
        run(async () => {
            const res = await api.auth.requestResetCode(form.email.trim());
            setInfo(res.message);
            setStep("code");
            setWait(RESEND_SECONDS);
        });
    };

    const checkCode = () => {
        const code = form.code.trim();
        if (!/^\d{6}$/.test(code)) { setErrs({ code: "Enter the 6-digit code from the email." }); return; }
        run(async () => {
            const res = await api.auth.verifyResetCode(form.email.trim(), code);
            setToken(res.reset_token);
            setInfo("");
            setStep("password");
        });
    };

    const savePassword = () => {
        const e = {};
        if (form.password.length < 6) e.password = "Password must be at least 6 characters.";
        else if (form.password !== form.confirm) e.confirm = "Passwords do not match.";
        if (Object.keys(e).length) { setErrs(e); return; }
        run(async () => {
            await api.auth.resetPassword(token, form.password);
            onDone(form.email.trim());
        });
    };

    const titles = {
        email: ["Forgot password?", "Enter your account email and we'll send you a verification code."],
        code: ["Enter verification code", `We sent a 6-digit code to ${form.email.trim()}. It is valid for 10 minutes.`],
        password: ["Set a new password", "Choose a new password for your account."],
    };

    return (
        <>
            <div style={{ fontWeight: 800, fontSize: "1.6rem", color: C.text, letterSpacing: "-0.03em", marginBottom: "0.35rem" }}>{titles[step][0]}</div>
            <div style={{ fontSize: "0.82rem", color: C.text2, marginBottom: "1.5rem" }}>{titles[step][1]}</div>

            {info && <div role="status" style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.25)", borderRadius: "10px", padding: "0.7rem 0.9rem", fontSize: "0.78rem", color: "#6ee7b7", marginBottom: "1rem" }}>{info}</div>}
            {formErr && <div role="alert" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: "10px", padding: "0.7rem 0.9rem", fontSize: "0.78rem", color: "#fca5a5", marginBottom: "1rem" }}>{formErr}</div>}

            {step === "email" && <>
                <AuthField fieldKey="email" label="Email Address" type="email" value={form.email} error={errs.email} onChange={handleChange} onSubmit={sendCode} />
                <button onClick={sendCode} disabled={busy} style={btnStyle(busy)}>{busy ? "Sending…" : "Send Verification Code →"}</button>
            </>}

            {step === "code" && <>
                <AuthField fieldKey="code" label="Verification Code" value={form.code} error={errs.code} onChange={handleChange} onSubmit={checkCode} transform={v => v.replace(/\D/g, "").slice(0, 6)} />
                <button onClick={checkCode} disabled={busy} style={btnStyle(busy)}>{busy ? "Checking…" : "Verify Code →"}</button>
                <p style={{ fontSize: "0.72rem", color: C.text3, marginTop: "1rem", textAlign: "center" }}>
                    Didn't get it? Check your spam folder, or{" "}
                    {wait > 0
                        ? <span>resend in {wait}s</span>
                        : <button type="button" style={linkBtn} onClick={sendCode} disabled={busy}>send a new code</button>}
                    {" · "}
                    <button type="button" style={linkBtn} onClick={() => { setStep("email"); setInfo(""); setFormErr(""); }}>change email</button>
                </p>
            </>}

            {step === "password" && <>
                <AuthField fieldKey="password" label="New Password" type="password" value={form.password} error={errs.password} onChange={handleChange} onSubmit={savePassword} showStrength />
                <AuthField fieldKey="confirm" label="Confirm New Password" type="password" value={form.confirm} error={errs.confirm} onChange={handleChange} onSubmit={savePassword} showStrength={false} />
                <button onClick={savePassword} disabled={busy} style={btnStyle(busy)}>{busy ? "Saving…" : "Reset Password →"}</button>
            </>}

            <p style={{ fontSize: "0.72rem", color: C.text3, marginTop: "1rem", textAlign: "center" }}>
                Remembered it? <button type="button" style={linkBtn} onClick={onBack}>Back to sign in</button>
            </p>
        </>
    );
}

// ─── SIGN IN / CREATE ACCOUNT ────────────────────────────────────────────────
export default function Signup() {
    const navigate = useNavigate();
    const [params, setParams] = useSearchParams();
    const { user, profile, ready, login, signup } = useAuth();
    const tab = ["signup", "forgot"].includes(params.get("tab")) ? params.get("tab") : "login";
    const [role, setRole] = useState("buyer");
    const [form, setForm] = useState({ email: "", password: "", name: "", cnic: "", mobile: "" });
    const [errs, setErrs] = useState({});
    const [formErr, setFormErr] = useState("");
    const [loading, setLoading] = useState(false);
    const [notice, setNotice] = useState("");

    // Signed in (now or already): go where the user was heading, else by role.
    useEffect(() => {
        if (!ready || !user || !profile) return;
        navigate(safeNext(params.get("next")) || (profile.role === "seller" ? "/dealer-dashboard" : "/properties"), { replace: true });
    }, [ready, user, profile, params, navigate]);

    // ── Single stable onChange handler — NO inline function components ──
    const handleChange = useCallback((key, value) => {
        setForm(f => ({ ...f, [key]: value }));
        setErrs(e => ({ ...e, [key]: "" }));
    }, []);

    const validate = () => {
        const e = {};
        if (tab === "signup") {
            if (!form.name || form.name.trim().length < 3) e.name = "Enter your full name.";
            if (!/^\d{5}-\d{7}-\d$/.test(form.cnic)) e.cnic = "Enter valid CNIC (XXXXX-XXXXXXX-X).";
            if (!/^0\d{3}-\d{7}$/.test(form.mobile)) e.mobile = "Enter valid Pakistan mobile number.";
        }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = "Enter a valid email address.";
        if (form.password.length < 6) e.password = "Password must be at least 6 characters.";
        setErrs(e); return Object.keys(e).length === 0;
    };

    const handleAuth = async () => {
        if (loading || !validate()) return;
        setLoading(true); setFormErr("");
        try {
            if (tab === "login") await login(form.email.trim(), form.password);
            else await signup({ email: form.email.trim(), password: form.password, name: form.name.trim(), cnic: form.cnic, mobile: form.mobile, role });
            // The redirect effect above takes over once the profile is loaded.
        } catch (e) {
            setFormErr(authErrorMessage(e));
            setLoading(false);
        }
    };

    const switchTab = (t) => {
        const next = new URLSearchParams(params);
        next.set("tab", t);
        setParams(next, { replace: true });
        setFormErr(""); setErrs({}); setNotice("");
    };

    const passwordWasReset = (email) => {
        switchTab("login");
        setForm(f => ({ ...f, email, password: "" }));
        setNotice("Your password has been changed. Sign in with your new password.");
    };

    return (
        <div className="auth-page" style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: "'Segoe UI',sans-serif", display: "grid", gridTemplateColumns: "1fr 1fr" }}>
            {/* Visual panel */}
            <div className="auth-visual" style={{ position: "relative", background: C.bg2, borderRight: `1px solid ${C.border}`, display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "3rem", overflow: "hidden" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <Link to="/" style={{ textDecoration: "none" }}><span style={{ fontWeight: 800, fontSize: "1.5rem", color: C.text, letterSpacing: "-0.03em" }}>HAVEN<span style={{ color: C.accent }}>.</span>AI</span></Link>
                </div>
                <div>
                    <h1 style={{ fontWeight: 800, fontSize: "2.2rem", color: C.text, lineHeight: 1.15, letterSpacing: "-0.03em", marginBottom: "0.75rem" }}>Find, Design &<br /><em style={{ fontStyle: "normal", color: C.accent }}>Own</em> your dream<br />home.</h1>
                    <p style={{ fontSize: "0.88rem", color: C.text2, lineHeight: 1.7, maxWidth: "340px" }}>Discover properties, talk to dealers directly, generate floor plans and 3D models, and restyle your rooms — all in one place.</p>
                </div>
                <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.6rem", fontSize: "0.8rem", color: C.text2 }}>
                    <li>🏠 Browse listings and message dealers</li>
                    <li>📐 AI-generated, validated 2D floor plans</li>
                    <li>🏛️ Interactive 3D models of your design</li>
                    <li>🎨 Restyle a photo of your own room</li>
                </ul>
            </div>

            {/* Form panel */}
            <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "3rem 2rem", background: C.bg, overflowY: "auto", position: "relative" }}>
                <button onClick={() => navigate("/")} title="Back to Home" aria-label="Back to Home" style={{ position: "absolute", top: "1.25rem", right: "1.25rem", width: 36, height: 36, borderRadius: "50%", background: C.surface, border: `1px solid ${C.border2}`, color: C.text2, fontSize: "1rem", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "inherit" }}>✕</button>

                <div style={{ width: "100%", maxWidth: "420px" }}>
                    {tab === "forgot" ? (
                        <ForgotPassword initialEmail={form.email} onBack={() => switchTab("login")} onDone={passwordWasReset} />
                    ) : <>
                    {/* Tabs */}
                    <div role="tablist" style={{ display: "flex", background: C.surface, border: `1px solid ${C.border2}`, borderRadius: "14px", padding: "4px", marginBottom: "2rem", gap: "4px" }}>
                        {["login", "signup"].map(t => (
                            <button key={t} role="tab" aria-selected={tab === t} onClick={() => switchTab(t)} style={{ flex: 1, textAlign: "center", padding: "0.7rem", borderRadius: "10px", fontWeight: 600, cursor: "pointer", border: "none", fontSize: "0.85rem", transition: "all 0.22s", background: tab === t ? C.accent : "none", color: tab === t ? "#fff" : C.text3, fontFamily: "inherit" }}>
                                {t === "login" ? "Sign In" : "Create Account"}
                            </button>
                        ))}
                    </div>

                    <div style={{ fontWeight: 800, fontSize: "1.6rem", color: C.text, letterSpacing: "-0.03em", marginBottom: "0.35rem" }}>{tab === "login" ? "Welcome back" : "Create account"}</div>
                    <div style={{ fontSize: "0.82rem", color: C.text2, marginBottom: "1.5rem" }}>{tab === "login" ? "Sign in to your Haven.AI account." : "Join Haven.AI — it's free to get started."}</div>

                    {/* Role selector (signup only) */}
                    {tab === "signup" && (
                        <div style={{ marginBottom: "1rem" }}>
                            <div style={{ display: "block", fontSize: "0.72rem", fontWeight: 600, color: C.text2, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: "0.5rem" }}>I want to</div>
                            <div role="radiogroup" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem", marginBottom: "0.5rem" }}>
                                {[["buyer", "🏠", "Buy / Rent", "Browse properties"], ["seller", "🏢", "Sell / List", "Upload properties"]].map(([r, ic, lb, sb]) => (
                                    <button type="button" role="radio" aria-checked={role === r} key={r} onClick={() => setRole(r)} style={{ background: role === r ? "rgba(59,130,246,0.08)" : C.surface, border: `1px solid ${role === r ? C.accent : C.border2}`, borderRadius: "11px", padding: "0.8rem 0.6rem", cursor: "pointer", textAlign: "center", color: C.text, fontFamily: "inherit" }}>
                                        <div style={{ fontSize: "1.4rem", marginBottom: "0.3rem" }}>{ic}</div>
                                        <div style={{ fontSize: "0.74rem", fontWeight: 600, color: C.text2 }}>{lb}</div>
                                        <div style={{ fontSize: "0.64rem", color: C.text3 }}>{sb}</div>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {notice && <div role="status" style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.25)", borderRadius: "10px", padding: "0.7rem 0.9rem", fontSize: "0.78rem", color: "#6ee7b7", marginBottom: "1rem" }}>{notice}</div>}
                    {formErr && <div role="alert" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: "10px", padding: "0.7rem 0.9rem", fontSize: "0.78rem", color: "#fca5a5", marginBottom: "1rem" }}>{formErr}</div>}

                    {/* Fields — using the stable AuthField component defined outside */}
                    {tab === "signup" && <>
                        <AuthField fieldKey="name" label="Full Name" value={form.name} error={errs.name} onChange={handleChange} onSubmit={handleAuth} />
                        <AuthField fieldKey="cnic" label="CNIC" value={form.cnic} error={errs.cnic} onChange={handleChange} onSubmit={handleAuth} transform={fmtCNIC} />
                        <AuthField fieldKey="mobile" label="Mobile Number" value={form.mobile} error={errs.mobile} onChange={handleChange} onSubmit={handleAuth} transform={fmtMobile} />
                    </>}
                    <AuthField fieldKey="email" label="Email Address" value={form.email} error={errs.email} onChange={handleChange} onSubmit={handleAuth} type="email" />
                    <AuthField fieldKey="password" label="Password" value={form.password} error={errs.password} onChange={handleChange} onSubmit={handleAuth} type="password" showStrength={tab === "signup"} />
                    {tab === "login" && (
                        <div style={{ textAlign: "right", margin: "-0.4rem 0 0.9rem" }}>
                            <button type="button" style={{ ...linkBtn, fontSize: "0.75rem" }} onClick={() => switchTab("forgot")}>Forgot password?</button>
                        </div>
                    )}

                    <button onClick={handleAuth} disabled={loading} style={btnStyle(loading)}>
                        {loading ? "Processing…" : tab === "login" ? "Sign In →" : "Create My Account →"}
                    </button>
                    <p style={{ fontSize: "0.72rem", color: C.text3, marginTop: "1rem", textAlign: "center" }}>
                        {tab === "login" ? "Don't have an account? " : "Already have an account? "}
                        <button type="button" style={{ color: C.accent2, cursor: "pointer", background: "none", border: "none", padding: 0, font: "inherit" }} onClick={() => switchTab(tab === "login" ? "signup" : "login")}>
                            {tab === "login" ? "Create one free" : "Sign in"}
                        </button>
                    </p>
                    </>}
                </div>
            </div>
        </div>
    );
}
