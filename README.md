# Haven.AI

AI-assisted housing platform (Final Year Project): ArchiBot chatbot, 2D floor
plans, 3D models, interior design on your own room photo, cost estimation,
and property listings with buyer ↔ dealer messaging.

| Folder | What it is |
|---|---|
| [`haven-ai-backend/`](haven-ai-backend/README.md) | FastAPI backend (Python): AI modules, auth checks, admin API |
| [`haven-ai-react/`](haven-ai-react/README.md) | React + Vite frontend |
| [`docs/`](docs/) | PRD, architecture, design, phase plan, development log |
| `firestore.rules` | Firestore security rules (`firebase deploy --only firestore:rules`) |

## Run locally

```bash
# 1. backend  (http://localhost:8000)
cd haven-ai-backend
python -m venv venv && venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env          # fill in GEMINI_API_KEY; add firebase-credentials.json
uvicorn app.main:app --reload

# 2. frontend (http://localhost:5000, proxies /api to the backend)
cd haven-ai-react
npm install
npm run dev
```

## First-time Firebase setup

1. Deploy the security rules from this folder: `firebase deploy --only firestore:rules`
   (needs the [Firebase CLI](https://firebase.google.com/docs/cli) and `firebase use <project-id>`).
2. Create your account on the website, then make it an administrator:
   `cd haven-ai-backend && python scripts/set_admin.py you@example.com`.
   Sign out and in again; the **Admin** link appears in the navigation bar.

## Deploy

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for a full walkthrough (backend on Render
via Docker, frontend on Vercel, Firebase rules and admin setup). Config lives in
[`render.yaml`](render.yaml), [`haven-ai-backend/Dockerfile`](haven-ai-backend/Dockerfile)
and [`haven-ai-react/vercel.json`](haven-ai-react/vercel.json).

## Tests

```bash
cd haven-ai-backend && python -m pytest
cd haven-ai-react && npm test && npm run lint
```
