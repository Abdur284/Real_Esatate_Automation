import { useEffect, useState } from 'react';
import api from '../../api';

// The signed-in user's saved interior designs: open one to keep editing it.

function Thumb({ path }) {
    const [url, setUrl] = useState(null);
    useEffect(() => {
        let alive = true;
        let made = null;
        api.interior.image(path).then((r) => { if (alive) { made = r.url; setUrl(r.url); } else URL.revokeObjectURL(r.url); })
            .catch(() => {});
        return () => { alive = false; if (made) URL.revokeObjectURL(made); };
    }, [path]);
    return url ? <img src={url} alt="" /> : <div className="ie-thumb-empty" />;
}

export default function SavedDesigns({ onOpen }) {
    const [designs, setDesigns] = useState(null);
    const [error, setError] = useState(null);
    const [opening, setOpening] = useState(null);
    const signedIn = !!api.interior.token();

    useEffect(() => {
        if (!signedIn) return;
        api.interior.designs.list().then((r) => setDesigns(r.designs)).catch((e) => setError(e.message));
    }, [signedIn]);

    if (!signedIn || (!designs?.length && !error)) return null;

    const open = async (d) => {
        setOpening(d.design_id);
        setError(null);
        try {
            onOpen(await api.interior.designs.open(d.design_id), d);
        } catch (e) {
            setError(e.message);
        } finally {
            setOpening(null);
        }
    };

    const remove = async (d) => {
        if (!window.confirm(`Delete “${d.name}”? This cannot be undone.`)) return;
        try {
            await api.interior.designs.remove(d.design_id);
            setDesigns((list) => list.filter((x) => x.design_id !== d.design_id));
        } catch (e) {
            setError(e.message);
        }
    };

    return (
        <section className="ie-saved">
            <h3>Your saved designs</h3>
            {error && <p className="ie-error">{error}</p>}
            <div className="ie-saved-grid">
                {(designs || []).map((d) => (
                    <div key={d.design_id} className="ie-saved-card">
                        <button type="button" className="ie-saved-open" onClick={() => open(d)} disabled={!!opening}>
                            <Thumb path={d.thumbnail_url} />
                            <strong>{d.name}</strong>
                            <span>{d.objects} objects · {d.updated_at ? new Date(d.updated_at).toLocaleDateString() : ''}</span>
                            {opening === d.design_id && <em>Opening…</em>}
                        </button>
                        <button type="button" className="ie-link is-danger" onClick={() => remove(d)}>Delete</button>
                    </div>
                ))}
            </div>
        </section>
    );
}
