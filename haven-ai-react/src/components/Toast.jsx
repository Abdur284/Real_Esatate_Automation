import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';

/**
 * App-wide notifications, replacing window.alert():
 *   const toast = useToast();  toast.success('Saved');  toast.error('Could not save');
 */
const ToastContext = createContext({ show: () => {}, success: () => {}, error: () => {} });

const TONES = {
    success: { icon: '✅', border: 'rgba(16,185,129,0.35)' },
    error: { icon: '⚠️', border: 'rgba(239,68,68,0.45)' },
    info: { icon: 'ℹ️', border: 'rgba(59,130,246,0.35)' },
};

export function ToastProvider({ children }) {
    const [items, setItems] = useState([]);
    const nextId = useRef(1);

    const dismiss = useCallback((id) => setItems((list) => list.filter((t) => t.id !== id)), []);

    const show = useCallback((message, tone = 'info') => {
        const id = nextId.current++;
        setItems((list) => [...list.slice(-3), { id, message, tone }]);
        setTimeout(() => dismiss(id), 4500);
    }, [dismiss]);

    const value = useMemo(() => ({
        show,
        success: (m) => show(m, 'success'),
        error: (m) => show(m, 'error'),
    }), [show]);

    return (
        <ToastContext.Provider value={value}>
            {children}
            <div aria-live="polite" style={{ position: 'fixed', bottom: '1.5rem', left: '1.5rem', zIndex: 2000, display: 'flex', flexDirection: 'column', gap: '0.6rem', maxWidth: 'calc(100vw - 3rem)' }}>
                {items.map((t) => (
                    <div key={t.id} role={t.tone === 'error' ? 'alert' : 'status'} onClick={() => dismiss(t.id)}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.7rem', background: 'var(--surface)', color: 'var(--text)', border: `1px solid ${TONES[t.tone].border}`, borderRadius: '12px', padding: '0.85rem 1.1rem', boxShadow: '0 16px 48px rgba(0,0,0,0.35)', fontSize: '0.88rem', maxWidth: '380px', cursor: 'pointer' }}>
                        <span>{TONES[t.tone].icon}</span>
                        <span>{t.message}</span>
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
    return useContext(ToastContext);
}
