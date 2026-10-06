// Layer toggles, storey filter and camera views for the 3D viewer.

const btn = (active) => ({
    background: active ? 'rgba(59,130,246,0.15)' : 'var(--surface)',
    border: `1.5px solid ${active ? 'rgba(59,130,246,0.5)' : 'var(--border)'}`,
    color: active ? 'var(--accent)' : 'var(--text-2)',
    padding: '0.4rem 0.8rem', borderRadius: '8px',
    fontFamily: 'Inter, sans-serif', fontSize: '0.76rem', fontWeight: 600,
    cursor: 'pointer', transition: 'all 0.2s',
});

const groupLabel = {
    fontSize: '0.66rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em',
    color: 'var(--text-3)', marginRight: '0.15rem',
};

const Sep = () => <div style={{ width: 1, height: 26, background: 'var(--border)' }} />;

const LAYER_TOGGLES = [
    ['showWalls', 'Walls'],
    ['showRoof', 'Roof'],
    ['transparentWalls', 'See-through'],
    ['showDoors', 'Doors'],
    ['showWindows', 'Windows'],
    ['showFurniture', 'Furniture'],
];

const VIEWS = [
    ['exterior', 'Exterior'],
    ['interior', 'Interior'],
    ['top', 'Top'],
    ['front', 'Front'],
    ['side', 'Side'],
    ['fit', 'Fit'],
];

export default function ModelToolbar({ layers, onToggle, storeys, levelFilter, onLevel, onView, onReset }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.9rem' }} role="toolbar" aria-label="3D model controls">
            <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={groupLabel}>Show</span>
                {LAYER_TOGGLES.map(([key, label]) => (
                    <button key={key} type="button" aria-pressed={Boolean(layers[key])}
                        onClick={() => onToggle(key)} style={btn(layers[key])}>
                        {layers[key] ? '▣' : '▢'} {label}
                    </button>
                ))}
            </div>
            <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={groupLabel}>Floor</span>
                <button type="button" onClick={() => onLevel('all')} style={btn(levelFilter === 'all')}>All</button>
                {storeys.map((s) => (
                    <button key={s.level} type="button" onClick={() => onLevel(String(s.level))}
                        style={btn(levelFilter === String(s.level))}>{s.label}</button>
                ))}
                <Sep />
                <span style={groupLabel}>View</span>
                {VIEWS.map(([name, label]) => (
                    <button key={name} type="button" onClick={() => onView(name)} style={btn(false)}>{label}</button>
                ))}
                <button type="button" onClick={onReset} style={btn(false)}>⟲ Reset</button>
            </div>
        </div>
    );
}
