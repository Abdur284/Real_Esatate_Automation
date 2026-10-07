import { Component } from 'react';

/** Shows a recoverable message instead of a blank page when a page crashes. */
export default class ErrorBoundary extends Component {
    state = { error: null };

    static getDerivedStateFromError(error) {
        return { error };
    }

    componentDidCatch(error, info) {
        console.error('Page crashed:', error, info.componentStack);
    }

    componentDidUpdate(prev) {
        // Navigating to another page clears the error.
        if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
    }

    render() {
        if (!this.state.error) return this.props.children;
        return (
            <div role="alert" className="page-content" style={{ padding: '8rem 2rem', textAlign: 'center' }}>
                <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>⚠️</div>
                <h2 style={{ fontFamily: 'Syne, sans-serif' }}>Something went wrong on this page</h2>
                <p style={{ color: 'var(--text-3)', margin: '1rem 0 2rem' }}>
                    Please try again. If it keeps happening, reload the page.
                </p>
                <button className="btn-cta" onClick={() => this.setState({ error: null })}>Try again</button>
            </div>
        );
    }
}
