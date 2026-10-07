import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

// The Firebase web config is public by design (it identifies the project, it
// does not grant access); what protects the data are the Firestore security
// rules in /firestore.rules. Values can be overridden per environment in
// .env.local (VITE_FIREBASE_*).
const env = import.meta.env;
const firebaseConfig = {
  apiKey: env.VITE_FIREBASE_API_KEY || "AIzaSyAJURwVDVWEXl_9NbebMDRxyIgriWGfL7Q",
  authDomain: env.VITE_FIREBASE_AUTH_DOMAIN || "website-d8f60.firebaseapp.com",
  projectId: env.VITE_FIREBASE_PROJECT_ID || "website-d8f60",
  storageBucket: env.VITE_FIREBASE_STORAGE_BUCKET || "website-d8f60.firebasestorage.app",
  messagingSenderId: env.VITE_FIREBASE_MESSAGING_SENDER_ID || "242761359928",
  appId: env.VITE_FIREBASE_APP_ID || "1:242761359928:web:1f170fb87244c4af5c3ccd"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
export default app;
