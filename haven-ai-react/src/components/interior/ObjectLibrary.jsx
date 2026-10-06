import { useEffect, useState } from 'react';
import api from '../../api';

// The object library: browse by category, search (also in plain words, e.g.
// "modern gray sofa"), filter by style / material / colour / size, sort, and
// pick an item to replace the selected object or add a new one.
// Everything is searched on the server a page at a time; previews are small
// cached images that load as they scroll into view.

const PAGE = 24;
const SORTS = [['relevance', 'Best match'], ['name', 'Name'], ['width_asc', 'Smallest first'], ['width_desc', 'Largest first']];
const FILTERS = [['realism', 'Model'], ['style', 'Style'], ['material', 'Material'], ['color', 'Colour'], ['size', 'Size']];

let categoriesCache = null;

function useDebounced(value, ms) {
    const [v, setV] = useState(value);
    useEffect(() => {
        const t = setTimeout(() => setV(value), ms);
        return () => clearTimeout(t);
    }, [value, ms]);
    return v;
}

function dims(d, unit) {
    return `${Math.round(d.width)} × ${Math.round(d.depth)} × ${Math.round(d.height)} ${unit}`;
}

function ItemCard({ item, actionLabel, onUse, busy }) {
    const [color, setColor] = useState(item.color);
    return (
        <article className="ol-card">
            <div className="ol-thumb">
                <img src={api.interior.library.url(item.thumbnail_url)} alt={item.name} loading="lazy" width="320" height="240" />
                {item.realism === 'real' && (
                    <span className="ol-badge" title="A 3D model of a real piece of furniture, with its real materials and size (CC0, Poly Haven)">
                        Real 3D model
                    </span>
                )}
            </div>
            <div className="ol-card-body">
                <strong>{item.name}</strong>
                <span className="ol-meta">{item.category_label} · {item.style.replace('-', ' ')} · {item.material_label}</span>
                {item.dimensions_source === 'measured' ? (
                    <span className="ol-dims" title="Measured from the 3D model of the real piece">
                        {dims(item.dimensions, item.unit)} <em>real size</em>
                    </span>
                ) : (
                    <span className="ol-dims" title="Typical size for this kind of piece, not a measured product">
                        {dims(item.dimensions, item.unit)} <em>typical</em>
                    </span>
                )}
                {item.colors.length > 1 && (
                    <div className="ol-colors" role="radiogroup" aria-label="Colour">
                        {item.colors.map((c) => (
                            <button key={c.hex + c.name} type="button" role="radio" aria-checked={color === c.hex}
                                className={color === c.hex ? 'is-on' : ''} style={{ background: c.hex }}
                                title={c.name} aria-label={c.name} onClick={() => setColor(c.hex)} />
                        ))}
                    </div>
                )}
                <button type="button" className="ie-btn is-primary ol-use" disabled={busy} onClick={() => onUse(item, color)}>
                    {actionLabel}
                </button>
            </div>
        </article>
    );
}

export default function ObjectLibrary({ mode, target, onUse, onClose, busy }) {
    const startCategory = mode === 'replace' ? target?.capabilities?.library_category || null : null;
    const [tree, setTree] = useState(categoriesCache);
    const [scope, setScope] = useState(startCategory ? { category: startCategory } : {});
    const [text, setText] = useState('');
    const [filters, setFilters] = useState({});
    const [sort, setSort] = useState('relevance');
    const [result, setResult] = useState(null);
    const [items, setItems] = useState([]);
    const [page, setPage] = useState(1);
    const [error, setError] = useState(null);
    const [loadedKey, setLoadedKey] = useState(null);
    const q = useDebounced(text, 300);
    const key = JSON.stringify({ q, scope, filters, sort, page });
    const loading = loadedKey !== key;

    useEffect(() => {
        if (categoriesCache) return;
        api.interior.library.categories()
            .then((t) => { categoriesCache = t; setTree(t); })
            .catch((e) => setError(e.message));
    }, []);

    // Search whenever what is asked changes; "Load more" asks for the next page.
    useEffect(() => {
        let alive = true;
        api.interior.library.search({ q, ...scope, ...filters, sort, page, page_size: PAGE })
            .then((r) => {
                if (!alive) return;
                setResult(r);
                setItems((prev) => (page === 1 ? r.items : [...prev, ...r.items]));
                setError(null);
                setLoadedKey(key);
            })
            .catch((e) => { if (alive) { setError(e.message); setLoadedKey(key); } });
        return () => { alive = false; };
    }, [key]);  // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        const onKey = (e) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [onClose]);

    const choose = (next) => { setScope(next); setFilters({}); setPage(1); };
    const setFilter = (key, value) => { setFilters((f) => ({ ...f, [key]: value || undefined })); setPage(1); };
    const scopeLabel = (() => {
        if (!tree) return '';
        for (const g of tree.groups) {
            if (scope.group === g.id) return g.label;
            const c = g.categories.find((x) => x.id === scope.category);
            if (c) return c.label;
        }
        return 'All objects';
    })();
    const interpreted = result?.interpreted;
    const understood = interpreted && ['realism', 'category', 'group', 'style', 'material', 'color', 'size']
        .map((k) => interpreted[k] && [k, k === 'realism' ? 'real 3D models' : interpreted[k]]).filter(Boolean);
    const title = mode === 'replace' ? `Change ${target?.label || 'object'}` : 'Add to the room';

    return (
        <div className="ie-modal" role="dialog" aria-label={title} onClick={(e) => e.target === e.currentTarget && onClose()}>
            <div className="ol-dialog">
                <header className="ol-head">
                    <div>
                        <strong>{title}</strong>
                        <span className="ie-hint">{mode === 'replace'
                            ? `The new piece takes its place and turn, scaled to about the size of this ${(target?.label || 'object').toLowerCase()}. You can resize it afterwards.`
                            : 'New pieces go on free floor (or wall / ceiling) space; drag them where you like.'}</span>
                    </div>
                    <button type="button" className="ol-close" onClick={onClose} aria-label="Close">×</button>
                </header>
                <div className="ol-search">
                    <input type="search" value={text} onChange={(e) => { setText(e.target.value); setPage(1); }}
                        placeholder='Search, e.g. "modern gray sofa" or "wooden coffee table"' aria-label="Search the library" autoFocus />
                </div>
                <div className="ol-body">
                    <nav className="ol-cats" aria-label="Categories">
                        <button type="button" className={!scope.category && !scope.group ? 'is-on' : ''} onClick={() => choose({})}>
                            Browse all <em>{tree?.total ?? ''}</em>
                        </button>
                        {tree?.groups.map((g) => (
                            <div key={g.id} className="ol-group">
                                <button type="button" className={`ol-group-btn${scope.group === g.id ? ' is-on' : ''}`}
                                    onClick={() => choose({ group: g.id })}>{g.label} <em>{g.count}</em></button>
                                {g.categories.map((c) => (
                                    <button key={c.id} type="button" className={scope.category === c.id ? 'is-on' : ''}
                                        onClick={() => choose({ category: c.id })}>{c.label} <em>{c.count}</em></button>
                                ))}
                            </div>
                        ))}
                    </nav>
                    <section className="ol-main">
                        <div className="ol-toolbar">
                            <span className="ol-scope">{scopeLabel}</span>
                            {FILTERS.map(([key, label]) => {
                                const options = result?.facets?.[key] || [];
                                if (options.length < 2 && !filters[key]) return null;
                                return (
                                    <select key={key} className="ie-select" value={filters[key] || ''} aria-label={label}
                                        onChange={(e) => setFilter(key, e.target.value)}>
                                        <option value="">{label}: any</option>
                                        {options.map((o) => <option key={o.value} value={o.value}>{o.label} ({o.count})</option>)}
                                    </select>
                                );
                            })}
                            <select className="ie-select" value={sort} aria-label="Sort" onChange={(e) => { setSort(e.target.value); setPage(1); }}>
                                {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                            </select>
                        </div>
                        {understood?.length > 0 && (
                            <p className="ol-understood">
                                Understood: {understood.map(([k, v]) => <span key={k} className="ie-chip">{String(v).replace(/_/g, ' ')}</span>)}
                                {result.relaxed?.length > 0 && <em> · nothing matched every word, so {result.relaxed.join(', ')} was relaxed</em>}
                            </p>
                        )}
                        {error && <p className="ie-error">{error}</p>}
                        <div className="ol-grid">
                            {items.map((it) => (
                                <ItemCard key={it.id} item={it} busy={busy}
                                    actionLabel={mode === 'replace' ? 'Use this' : 'Add'} onUse={onUse} />
                            ))}
                        </div>
                        {!loading && result && items.length === 0 && <p className="ie-hint">Nothing in the library matches that. Try fewer words or Browse all.</p>}
                        <div className="ol-footer">
                            <span className="ie-hint">{result ? `Showing ${items.length} of ${result.total}` : ''}</span>
                            {loading && <span className="ie-spinner" aria-label="Loading" />}
                            {!loading && result && items.length < result.total && (
                                <button type="button" className="ie-btn" onClick={() => setPage((p) => p + 1)}>Load more</button>
                            )}
                        </div>
                    </section>
                </div>
            </div>
        </div>
    );
}
