# Haven.AI frontend

React 19 + Vite. In development the Vite server (port 5000) proxies `/api` to
the backend on port 8000.

```bash
npm install
npm run dev        # http://localhost:5000
npm test           # vitest
npm run lint       # eslint
npm run build      # production build in dist/
```

Configuration: copy `.env.example` to `.env.local`. In production set
`VITE_API_BASE_URL` to the backend's URL.

## Structure

```
src/
  App.jsx                 routes (pages are lazy-loaded), providers
  api.js                  every backend call; adds the user's Firebase ID token
  firebase.js             Firebase app, Auth and Firestore
  auth/
    AuthContext.jsx       who is signed in (Firebase Auth SDK): user, profile, isAdmin
    ProtectedRoute.jsx    sign-in / seller / admin gates for routes
  components/
    Layout.jsx            navbar + page + footer for every route
    ErrorBoundary.jsx     recoverable error screen instead of a blank page
    Toast.jsx             notifications (useToast) instead of alert()
    Markdown.jsx          safe rendering of the assistant's Markdown replies
    ...                   feature components (interior/, threeD/, chat widgets)
  pages/                  one file per route
```

## Auth and data access

* Sign-in uses the **Firebase Auth SDK** only (`useAuth()`); tokens refresh
  automatically and are attached to API calls by `api.js`.
* Listings, profiles and buyer ↔ dealer chats are read/written directly in
  Firestore and protected by `/firestore.rules` in the repository root.
* Admin actions go through the backend (`/api/admin/*`), which checks the
  `admin` custom claim.
