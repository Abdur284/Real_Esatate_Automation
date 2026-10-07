import AIChat from '../components/AIChat';

export default function CostEstimation() {
    return (
        <>
            <section className="page-hero">
                <div className="page-hero-inner">
                    <div className="page-hero-icon">💰</div>
                    <div>
                        <h1>Cost Estimation</h1>
                        <p>Get transparent, itemized AI cost breakdowns for any construction or renovation project before you commit.</p>
                    </div>
                </div>
            </section>
            <div className="page-content">
                <AIChat
                    title="Cost Estimation AI"
                    icon="💰"
                    welcomeText="Describe your project and I'll generate a detailed, itemized cost breakdown — covering materials, labor, and timeline — so you can plan with confidence."
                    placeholder="e.g. Build a 3-bedroom house, 1800 sq ft, mid-range finishes..."
                    chips={['New house construction budget', 'Kitchen renovation cost', 'Bathroom remodel estimate', 'Compare material costs']}
                    systemContext=""
                />
                <div className="info-panel">
                    <div className="info-card">
                        <div className="info-card-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
                        </div>
                        <div>
                            <h4>What can you ask?</h4>
                            <p>Provide project type (new build, renovation, extension), size, location, and finish quality (budget / mid-range / luxury). The AI will break down costs by category.</p>
                        </div>
                    </div>
                    <div className="info-card">
                        <div className="info-card-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
                        </div>
                        <div>
                            <h4>Disclaimer</h4>
                            <p>AI estimates are for planning purposes only. Always get quotes from licensed contractors before making financial commitments. Regional costs vary significantly.</p>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}
