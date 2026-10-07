import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import Markdown from './Markdown';

const show = (text) => render(<MemoryRouter><Markdown text={text} /></MemoryRouter>);

describe('Markdown (assistant replies)', () => {
    it('renders headings, lists, emphasis and tables', () => {
        show('### Estimate\n\n- **Total**: PKR 10\n- *rough*\n\n| Item | Cost |\n|---|---|\n| Labour | 5 |');
        expect(screen.getByRole('heading', { name: 'Estimate' })).toBeInTheDocument();
        expect(screen.getAllByRole('listitem')).toHaveLength(2);
        expect(screen.getByText('Total').tagName).toBe('STRONG');
        expect(screen.getByRole('table')).toBeInTheDocument();
        expect(screen.getByRole('cell', { name: 'Labour' })).toBeInTheDocument();
    });

    it('keeps site and http(s) links but drops javascript: links', () => {
        show('[Listing](/property/abc) [Docs](https://example.com) [Bad](javascript:alert(1))');
        expect(screen.getByRole('link', { name: 'Listing' })).toHaveAttribute('href', '/property/abc');
        expect(screen.getByRole('link', { name: 'Docs' })).toHaveAttribute('rel', 'noopener noreferrer');
        expect(screen.queryByRole('link', { name: 'Bad' })).toBeNull();
        expect(screen.getByText(/Bad/)).toBeInTheDocument();
    });

    it('never interprets HTML in the text', () => {
        const { container } = show('<img src=x onerror=alert(1)> hello');
        expect(container.querySelector('img')).toBeNull();
        expect(screen.getByText(/<img src=x/)).toBeInTheDocument();
    });
});
