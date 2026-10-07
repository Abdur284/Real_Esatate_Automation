import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import {
    createUserWithEmailAndPassword,
    onAuthStateChanged,
    signInWithEmailAndPassword,
    signOut,
    updateProfile,
} from 'firebase/auth';
import { doc, getDoc, serverTimestamp, setDoc } from 'firebase/firestore';
import { auth, db } from '../firebase';
import { setTokenProvider } from '../api';

/**
 * The one source of truth for who is signed in (Firebase Auth SDK).
 *
 *   user     Firebase user, or null for guests
 *   profile  { name, email, role } from users/{uid}
 *   isAdmin  the `admin` custom claim (granted server-side by scripts/set_admin.py)
 *   ready    false until Firebase has restored the session on page load
 *
 * ID tokens come from user.getIdToken(), which refreshes them automatically.
 */
const GUEST = { user: null, profile: null, isAdmin: false, ready: true };

const AuthContext = createContext({
    ...GUEST,
    login: async () => { throw new Error('Auth is not available.'); },
    signup: async () => { throw new Error('Auth is not available.'); },
    logout: async () => {},
});

const ERRORS = {
    'auth/invalid-credential': 'Incorrect email or password.',
    'auth/wrong-password': 'Incorrect email or password.',
    'auth/user-not-found': 'No account found. Please sign up.',
    'auth/email-already-in-use': 'Email already in use.',
    'auth/weak-password': 'Password too weak (min 6 characters).',
    'auth/invalid-email': 'Enter a valid email address.',
    'auth/too-many-requests': 'Too many attempts. Please wait a moment and try again.',
    'auth/network-request-failed': 'Could not reach the sign-in service. Check your connection.',
};

// eslint-disable-next-line react-refresh/only-export-components
export function authErrorMessage(err) {
    return ERRORS[err?.code] || 'Something went wrong. Please try again.';
}

async function loadProfile(fbUser, pending) {
    try {
        const snap = await getDoc(doc(db, 'users', fbUser.uid));
        // Right after sign-up the profile document may not be written yet.
        const d = snap.exists() ? snap.data() : (pending || {});
        return { name: d.name || fbUser.displayName || 'User', email: fbUser.email, role: d.role || 'buyer' };
    } catch {
        return { name: fbUser.displayName || 'User', email: fbUser.email, role: 'buyer' };
    }
}

export function AuthProvider({ children }) {
    const [state, setState] = useState({ user: null, profile: null, isAdmin: false, ready: false });
    const pendingSignup = useRef(null);

    useEffect(() => onAuthStateChanged(auth, async (fbUser) => {
        if (!fbUser) {
            setTokenProvider(null);
            setState({ ...GUEST });
            return;
        }
        setTokenProvider(() => fbUser.getIdToken());
        const [profile, token] = await Promise.all([loadProfile(fbUser, pendingSignup.current), fbUser.getIdTokenResult()]);
        setState({ user: fbUser, profile, isAdmin: token.claims.admin === true, ready: true });
    }), []);

    const login = useCallback(async (email, password) => {
        await signInWithEmailAndPassword(auth, email, password);
    }, []);

    const signup = useCallback(async ({ email, password, name, cnic, mobile, role }) => {
        pendingSignup.current = { name, email, role };
        try {
            const cred = await createUserWithEmailAndPassword(auth, email, password);
            await updateProfile(cred.user, { displayName: name });
            await setDoc(doc(db, 'users', cred.user.uid), {
                name, cnic, mobile, email, role, createdAt: serverTimestamp(),
            });
        } finally {
            pendingSignup.current = null;
        }
    }, []);

    const logout = useCallback(() => signOut(auth), []);

    const value = useMemo(() => ({ ...state, login, signup, logout }), [state, login, signup, logout]);
    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
    return useContext(AuthContext);
}
