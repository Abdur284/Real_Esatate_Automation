import { Fragment } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * Renders the Markdown the AI assistant answers with: headings, bullet and
 * numbered lists, tables, **bold**, *italic*, `code`, links and rules.
 * Everything becomes React elements (no innerHTML), and links are only
 * followed when they are site paths or http(s) URLs, so model output can
 * never inject markup or javascript: URLs.
 */

const SAFE_EXTERNAL = /^https?:\/\//i;

function Inline({ text }) {
    const navigate = useNavigate();
    const out = [];
    // links | bold | italic (* or _) | inline code
    const re = /\[([^\]]+)\]\(([^)\s]+)\)|\*\*([^*]+)\*\*|\*([^*\s][^*]*)\*|_([^_\s][^_]*)_|`([^`]+)`/g;
    let last = 0;
    let m;
    while ((m = re.exec(text)) !== null) {
        if (m.index > last) out.push(text.slice(last, m.index));
        const key = `${m.index}`;
        if (m[1] !== undefined) {
            const href = m[2];
            if (href.startsWith('/') && !href.startsWith('//')) {
                out.push(<a key={key} href={href} onClick={(e) => { e.preventDefault(); navigate(href); }}>{m[1]}</a>);
            } else if (SAFE_EXTERNAL.test(href)) {
                out.push(<a key={key} href={href} target="_blank" rel="noopener noreferrer">{m[1]}</a>);
            } else {
                out.push(m[1]);
            }
        } else if (m[3] !== undefined) out.push(<strong key={key}>{m[3]}</strong>);
        else if (m[4] !== undefined) out.push(<em key={key}>{m[4]}</em>);
        else if (m[5] !== undefined) out.push(<em key={key}>{m[5]}</em>);
        else if (m[6] !== undefined) out.push(<code key={key}>{m[6]}</code>);
        last = re.lastIndex;
    }
    if (last < text.length) out.push(text.slice(last));
    return <>{out}</>;
}

const cells = (row) => row.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());

/** Splits the text into blocks: heading, list, table, rule, paragraph. */
function parse(text) {
    const lines = String(text || '').replace(/\r\n/g, '\n').split('\n');
    const blocks = [];
    let i = 0;
    while (i < lines.length) {
        const line = lines[i];
        if (!line.trim()) { i++; continue; }
        let m;
        if ((m = line.match(/^\s*(#{1,6})\s+(.*)$/))) {
            blocks.push({ type: 'heading', level: m[1].length, text: m[2] });
            i++;
        } else if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
            blocks.push({ type: 'rule' });
            i++;
        } else if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
            const head = cells(line);
            const rows = [];
            i += 2;
            while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(cells(lines[i++]));
            blocks.push({ type: 'table', head, rows });
        } else if (/^\s*([-*•]|\d+[.)])\s+/.test(line)) {
            const ordered = /^\s*\d+[.)]\s+/.test(line);
            const items = [];
            while (i < lines.length && /^\s*([-*•]|\d+[.)])\s+/.test(lines[i])) {
                items.push(lines[i].replace(/^\s*([-*•]|\d+[.)])\s+/, ''));
                i++;
            }
            blocks.push({ type: 'list', ordered, items });
        } else {
            const para = [];
            while (i < lines.length && lines[i].trim() && !/^\s*(#{1,6}\s|[-*•]\s|\d+[.)]\s|\|)/.test(lines[i])) para.push(lines[i++]);
            if (!para.length) para.push(lines[i++]);
            blocks.push({ type: 'paragraph', lines: para });
        }
    }
    return blocks;
}

export default function Markdown({ text }) {
    return (
        <div className="md">
            {parse(text).map((b, bi) => {
                switch (b.type) {
                    case 'heading': {
                        const Tag = `h${Math.min(b.level + 2, 6)}`;
                        return <Tag key={bi}><Inline text={b.text} /></Tag>;
                    }
                    case 'rule':
                        return <hr key={bi} />;
                    case 'table':
                        return (
                            <div key={bi} className="md-table-wrap">
                                <table>
                                    <thead><tr>{b.head.map((h, hi) => <th key={hi}><Inline text={h} /></th>)}</tr></thead>
                                    <tbody>{b.rows.map((r, ri) => <tr key={ri}>{r.map((c, ci) => <td key={ci}><Inline text={c} /></td>)}</tr>)}</tbody>
                                </table>
                            </div>
                        );
                    case 'list': {
                        const Tag = b.ordered ? 'ol' : 'ul';
                        return <Tag key={bi}>{b.items.map((it, ii) => <li key={ii}><Inline text={it} /></li>)}</Tag>;
                    }
                    default:
                        return (
                            <p key={bi}>
                                {b.lines.map((l, li) => (
                                    <Fragment key={li}>{li > 0 && <br />}<Inline text={l} /></Fragment>
                                ))}
                            </p>
                        );
                }
            })}
        </div>
    );
}
