// Draws one floor of a 2D plan returned by POST /api/design/2d/generate.
// The SVG viewBox is in feet, so plan coordinates are used directly; only the
// y axis is flipped, because the plan's origin is the plot's bottom-left corner
// (road side at the bottom) while SVG's origin is top-left.
import { ROOM_COLORS } from './floorPlanColors';

const OPEN_TYPES = new Set(['courtyard', 'lawn', 'terrace', 'balcony', 'setback', 'parking']);
const INK = '#1e293b';
const PAPER = '#ffffff';

function openingSegment(item, op, L) {
    // Returns [x1, y1, x2, y2] in SVG coordinates for an opening on one wall.
    const { x, y, width: w, length: l } = item;
    const off = Number(op.offset_ft) || 0;
    const ow = Number(op.width_ft) || 3;
    const top = L - (y + l);     // SVG y of the room's north wall
    const bottom = L - y;        // SVG y of the room's south wall
    switch (String(op.wall).toLowerCase()) {
        case 'south': return [x + off, bottom, x + off + ow, bottom];
        case 'north': return [x + off, top, x + off + ow, top];
        case 'west':  return [x, bottom - off, x, bottom - off - ow];
        case 'east':  return [x + w, bottom - off, x + w, bottom - off - ow];
        default: return null;
    }
}

function Label({ item, L }) {
    const { x, y, width: w, length: l, name = '' } = item;
    const cx = x + w / 2;
    const cy = L - (y + l / 2);
    // Shrink text to fit narrow rooms; ~0.55 ft per character at size 1.
    const size = Math.max(0.45, Math.min(1.05, (w - 0.6) / Math.max(name.length * 0.55, 1), l / 3.2));
    const vertical = w < 5 && l > w * 1.8;
    return (
        <g transform={vertical ? `rotate(-90 ${cx} ${cy})` : undefined} pointerEvents="none">
            <text x={cx} y={cy - size * 0.15} textAnchor="middle" fontSize={size} fontWeight="700" fill={INK}
                fontFamily="Inter, sans-serif">{name}</text>
            <text x={cx} y={cy + size * 1.05} textAnchor="middle" fontSize={size * 0.8} fill="#475569"
                fontFamily="Inter, sans-serif">{`${w}′ × ${l}′`}</text>
        </g>
    );
}

export default function FloorPlanViewer({ plot, floor, selected, onSelect }) {
    const W = Number(plot.width_ft);
    const L = Number(plot.length_ft);
    const pad = 4;
    const items = ['open_spaces', 'circulation', 'rooms'].flatMap((section) =>
        (floor?.[section] || [])
            .filter((it) => [it.x, it.y, it.width, it.length].every((v) => typeof v === 'number'))
            .map((it, i) => ({ ...it, _key: `${section}-${i}`, _section: section })));

    return (
        <svg viewBox={`${-pad} ${-pad} ${W + pad * 2} ${L + pad * 2 + 2}`} role="img"
            aria-label="2D floor plan" style={{ width: '100%', height: 'auto', display: 'block', background: PAPER }}>
            <defs>
                <pattern id="fp-hatch" width="1.2" height="1.2" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                    <line x1="0" y1="0" x2="0" y2="1.2" stroke="#94a3b8" strokeWidth="0.12" />
                </pattern>
            </defs>

            {/* Plot boundary */}
            <rect x={0} y={0} width={W} height={L} fill="#f8fafc" stroke="#64748b" strokeWidth={0.15} strokeDasharray="0.8 0.5" />

            {items.map((it) => {
                const open = it._section === 'open_spaces' || OPEN_TYPES.has(it.type);
                const isSel = selected === it._key;
                return (
                    <g key={it._key} onClick={() => onSelect?.(isSel ? null : it._key)} style={{ cursor: 'pointer' }}>
                        <title>{`${it.name} — ${it.width} × ${it.length} ft${it.purpose ? `\n${it.purpose}` : ''}`}</title>
                        <rect x={it.x} y={L - (it.y + it.length)} width={it.width} height={it.length}
                            fill={ROOM_COLORS[it.type] || ROOM_COLORS.other}
                            stroke={isSel ? '#2563eb' : INK}
                            strokeWidth={isSel ? 0.45 : open ? 0.12 : 0.35}
                            strokeDasharray={open ? '0.6 0.4' : undefined} />
                        {open && <rect x={it.x} y={L - (it.y + it.length)} width={it.width} height={it.length}
                            fill="url(#fp-hatch)" opacity={0.35} pointerEvents="none" />}
                        {it.type === 'staircase' && Array.from({ length: Math.floor(it.length / 1) }, (_, k) => (
                            <line key={k} x1={it.x} x2={it.x + it.width}
                                y1={L - it.y - (k + 0.5)} y2={L - it.y - (k + 0.5)}
                                stroke="#a16207" strokeWidth={0.06} pointerEvents="none" />
                        ))}
                    </g>
                );
            })}

            {/* Openings drawn after all rooms so shared walls don't paint over them */}
            {items.flatMap((it) => [
                ...(it.windows || []).map((op, i) => {
                    const s = openingSegment(it, op, L);
                    return s && (
                        <g key={`${it._key}-w${i}`} pointerEvents="none">
                            <line x1={s[0]} y1={s[1]} x2={s[2]} y2={s[3]} stroke="#0ea5e9" strokeWidth={0.55} />
                            <line x1={s[0]} y1={s[1]} x2={s[2]} y2={s[3]} stroke={PAPER} strokeWidth={0.18} />
                        </g>
                    );
                }),
                ...(it.doors || []).map((op, i) => {
                    const s = openingSegment(it, op, L);
                    return s && (
                        <g key={`${it._key}-d${i}`} pointerEvents="none">
                            <line x1={s[0]} y1={s[1]} x2={s[2]} y2={s[3]} stroke={PAPER} strokeWidth={0.5} />
                            <line x1={s[0]} y1={s[1]} x2={s[2]} y2={s[3]} stroke="#d97706" strokeWidth={0.22}
                                strokeDasharray={op.to === 'Outside' ? undefined : '0.35 0.2'} />
                        </g>
                    );
                }),
            ])}

            {items.map((it) => <Label key={`${it._key}-l`} item={it} L={L} />)}

            {/* Plot dimensions and road marker */}
            <text x={W / 2} y={-1.3} textAnchor="middle" fontSize={1} fill="#475569" fontFamily="Inter, sans-serif">{W} ft</text>
            <text x={-1.3} y={L / 2} textAnchor="middle" fontSize={1} fill="#475569" fontFamily="Inter, sans-serif"
                transform={`rotate(-90 ${-1.3} ${L / 2})`}>{L} ft</text>
            <text x={W / 2} y={L + 2.6} textAnchor="middle" fontSize={1} fontWeight="700" fill="#475569"
                letterSpacing="0.3" fontFamily="Inter, sans-serif">ROAD / FRONT</text>
        </svg>
    );
}
