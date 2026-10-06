import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: "AIzaSyAJURwVDVWEXl_9NbebMDRxyIgriWGfL7Q",
  authDomain: "website-d8f60.firebaseapp.com",
  projectId: "website-d8f60",
  storageBucket: "website-d8f60.firebasestorage.app",
  messagingSenderId: "242761359928",
  appId: "1:242761359928:web:1f170fb87244c4af5c3ccd"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
export default app;
