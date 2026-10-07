import { useEffect, useState } from 'react';
import AIChat from '../components/AIChat';
import api from '../api';
import RoomUpload from '../components/interior/RoomUpload';
import RoomEditor from '../components/interior/RoomEditor';
import SavedDesigns from '../components/interior/SavedDesigns';

const LAST_SCENE_KEY = 'haven.interior.scene';

export default function InteriorDesign() {
    const [session, setSession] = useState(null);      // scene response from the API
    const [design, setDesign] = useState(null);        // saved design it came from, if any
    const [catalog, setCatalog] = useState(null);
    const [catalogError, setCatalogError] = useState(null);

    useEffect(() => {
        api.interior.catalog().then(setCatalog)
            .catch(() => setCatalogError('The interior design service is not reachable. Please make sure the backend is running.'));
        // Coming back to the page (or reloading it) reopens the room being edited.
        let last = null;
        try { last = sessionStorage.getItem(LAST_SCENE_KEY); } catch { /* storage unavailable */ }
        if (last) api.interior.scene(last).then(setSession).catch(() => {
            try { sessionStorage.removeItem(LAST_SCENE_KEY); } catch { /* ignore */ }
        });
    }, []);

    const close = () => {
        try { sessionStorage.removeItem(LAST_SCENE_KEY); } catch { /* ignore */ }
        setSession(null);
        setDesign(null);
    };

    return (
        <>
            <section className="page-hero">
                <div className="page-hero-inner">
                    <div className="page-hero-icon">🎨</div>
                    <div>
                        <h1>Interior Design</h1>
                        <p>Upload a photo of your room, then move, resize, recolour, re-floor and swap the furniture — and see the result on your own room.</p>
                    </div>
                </div>
            </section>

            <div className="ie-wrap">
                {catalogError && <p className="ie-error">{catalogError}</p>}
                {session && catalog ? (
                    <RoomEditor key={session.scene.scene_id} initial={session} design={design} catalog={catalog} onClose={close} />
                ) : (
                    <>
                        <RoomUpload onAnalyzed={(res) => { setDesign(null); setSession(res); }} />
                        <SavedDesigns onOpen={(res, d) => { setDesign(d); setSession(res); }} />
                    </>
                )}
            </div>

            <div className="page-content">
                <AIChat
                    title="Interior Design AI"
                    icon="🎨"
                    welcomeText="Need ideas first? Tell me about your space, style preferences, and budget — I'll suggest a complete concept with colors, furniture, lighting, and décor."
                    placeholder="e.g. Scandinavian living room, 20 sqm, neutral tones, cozy and minimalist feel, medium budget..."
                    chips={['Scandinavian living room', 'Luxury master bedroom', 'Industrial kitchen design', 'Small apartment makeover']}
                    systemContext="You are a world-class interior design AI consultant with expertise across all styles — modern, minimalist, Scandinavian, bohemian, industrial, traditional, Art Deco, and more. When given a design brief, provide: a complete color palette with hex codes, furniture recommendations with approximate price points, flooring and wall treatment ideas, lighting design (ambient, task, accent), textile and soft furnishing suggestions, art and décor recommendations, and a room layout strategy. Be specific, inspiring, and practical."
                />

                <div className="info-panel">
                    <div className="info-card">
                        <div className="info-card-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
                        </div>
                        <div>
                            <h4>How the room editor works</h4>
                            <p>The photo is analysed once to find walls, floor, ceiling, furniture and decor. After that every change — moving, resizing, recolouring, new flooring — is applied to that structured room and redrawn on your photo, so nothing else changes.</p>
                        </div>
                    </div>
                    <div className="info-card">
                        <div className="info-card-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>
                        </div>
                        <div>
                            <h4>Tip for best results</h4>
                            <p>Use a bright, sharp photo taken from a corner or doorway with the floor visible. Sizes are estimated from the furniture in the photo, so they are approximate.</p>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}
