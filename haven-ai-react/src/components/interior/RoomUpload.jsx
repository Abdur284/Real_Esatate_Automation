import { useEffect, useRef, useState } from 'react';
import api from '../../api';
import { MAX_MB, checkDimensions, checkFile } from './uploadCheck';

// Step 1: choose a room photo, check it, preview it, send it for analysis.
// The browser checks type, size and dimensions for a quick answer; the
// server checks again from the file's content (the browser can be wrong).

function readSize(url) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
        img.onerror = () => reject(new Error('This file could not be opened as an image.'));
        img.src = url;
    });
}

const STEPS = ['Checking the photo', 'Finding walls, floor and ceiling', 'Finding furniture and decor', 'Building the editable room'];

export default function RoomUpload({ onAnalyzed }) {
    const [file, setFile] = useState(null);
    const [preview, setPreview] = useState(null);
    const [size, setSize] = useState(null);
    const [error, setError] = useState(null);
    const [phase, setPhase] = useState('idle');       // idle | ready | uploading | analyzing
    const [progress, setProgress] = useState(0);
    const [step, setStep] = useState(0);
    const [dragOver, setDragOver] = useState(false);
    const inputRef = useRef(null);

    useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

    useEffect(() => {
        if (phase !== 'analyzing') return undefined;
        const t = setInterval(() => setStep((s) => Math.min(STEPS.length - 1, s + 1)), 1400);
        return () => clearInterval(t);
    }, [phase]);

    const pick = async (f) => {
        setError(null);
        const problem = checkFile(f);
        if (problem) { setError(problem); setFile(null); setPreview(null); setPhase('idle'); return; }
        const url = URL.createObjectURL(f);
        try {
            const dims = await readSize(url);
            const tooSmall = checkDimensions(dims);
            if (tooSmall) {
                URL.revokeObjectURL(url);
                setError(tooSmall);
                return;
            }
            setSize(dims);
        } catch (e) {
            URL.revokeObjectURL(url);
            setError(e.message);
            return;
        }
        setFile(f);
        setPreview(url);
        setPhase('ready');
    };

    const analyze = async () => {
        if (!file) return;
        setError(null);
        setProgress(0);
        setStep(0);
        setPhase('uploading');
        try {
            const res = await api.interior.analyze(file, (p) => {
                setProgress(p);
                if (p >= 1) setPhase('analyzing');
            });
            onAnalyzed(res);
        } catch (e) {
            setError(e.message);
            setPhase('ready');
        }
    };

    const working = phase === 'uploading' || phase === 'analyzing';

    return (
        <div className="ie-upload">
            <div
                className={`ie-drop${dragOver ? ' is-over' : ''}${preview ? ' has-preview' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => { e.preventDefault(); setDragOver(false); if (!working) pick(e.dataTransfer.files?.[0]); }}
                onClick={() => !working && !preview && inputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !working) inputRef.current?.click(); }}
                aria-label="Choose a room photo"
            >
                {preview ? (
                    <img src={preview} alt="Selected room" className="ie-preview" />
                ) : (
                    <div className="ie-drop-inner">
                        <div className="ie-drop-icon" aria-hidden="true">📷</div>
                        <strong>Upload a photo of your room</strong>
                        <span>Drop it here or click to choose · JPG, PNG or WebP · up to {MAX_MB} MB</span>
                        <span className="ie-hint">Best results: a well-lit photo from a corner or doorway, showing the floor.</span>
                    </div>
                )}
                {working && (
                    <div className="ie-progress-overlay">
                        {phase === 'uploading' ? (
                            <>
                                <div className="ie-progress"><div style={{ width: `${Math.round(progress * 100)}%` }} /></div>
                                <span>Uploading… {Math.round(progress * 100)}%</span>
                            </>
                        ) : (
                            <>
                                <span className="ie-spinner is-large" />
                                <span>{STEPS[step]}…</span>
                            </>
                        )}
                    </div>
                )}
            </div>
            <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" hidden
                onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ''; }} />

            {error && <p className="ie-error" role="alert">{error}</p>}

            {preview && (
                <div className="ie-upload-actions">
                    <span className="ie-hint">{file?.name} · {size ? `${size.width}×${size.height}` : ''} · {(file.size / 1024 / 1024).toFixed(1)} MB</span>
                    <button type="button" className="ie-btn" disabled={working} onClick={() => inputRef.current?.click()}>Choose another</button>
                    <button type="button" className="ie-btn is-primary" disabled={working} onClick={analyze}>
                        {working ? 'Analysing…' : 'Analyse room'}
                    </button>
                </div>
            )}
        </div>
    );
}
