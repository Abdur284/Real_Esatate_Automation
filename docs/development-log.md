# AI-Powered Real Estate Platform
## Project Memory

**Document:** `memory.md`
**Version:** 1.0
**Purpose:** Persistent project context, decisions, progress, issues, and current development state

---

# 1. Memory

## 1.1 Purpose

This file maintains important project context that should remain available across development sessions.

The purpose is to:

- Preserve important project decisions.
- Remember project-specific preferences.
- Track architectural patterns.
- Track completed features.
- Track current development work.
- Record important issues and their solutions.
- Prevent repeated mistakes.
- Maintain consistency between development sessions.
- Help AI coding agents understand the current project state.

This file must contain **important and reusable information only**.

Do not use this file as a general conversation history.

---

# 1.2 Project Identity

Project Type:

```text
Final Year Project

Project Description:

AI-Powered Real Estate Platform

Core purpose:

Provide a unified real-estate platform that combines
property management, property search, AI assistance,
property recommendations, architectural/design tools,
construction cost estimation, and user-dealer communication.
1.3 Core Project Modules

The project contains the following major modules:

1. Authentication
2. User Module
3. Dealer Module
4. Admin Module
5. Property Management
6. Property Search
7. Property Recommendation
8. Centralized AI Chatbot
9. AI Intent Detection
10. AI Request Routing
11. 2D Design
12. 3D Design
13. Interior Design
14. Construction Cost Estimation
15. User-Dealer Chat
16. Notifications
17. File Upload/Download
18. User Settings
19. Dashboard
20. Analytics
1.4 User Roles

The system supports the following roles:

VISITOR
USER
DEALER
ADMIN
Visitor

Can access public functionality.

Cannot access protected user, dealer, or admin functionality.

User

Can:

Manage their profile.
Search properties.
View properties.
Receive property recommendations.
Use the centralized AI chatbot.
Use 2D design.
Use 3D design.
Use interior design.
Use construction cost estimation.
Chat with dealers.
Manage appropriate preferences.
Dealer

Can:

Manage dealer profile.
Create properties.
View properties.
Update their own properties.
Delete their own properties.
Receive user inquiries.
Chat with users.
Admin

Can:

Manage users.
Manage dealers.
Manage properties.
View administrative statistics.
Monitor platform activity.
Perform authorized administrative operations.

Admin functionality must never be accessible to normal users.

1.5 Technology Decisions

IMPORTANT: the approved stack and the stack actually implemented are NOT the
same. Both are recorded here deliberately. Per 5.3 of this document a conflict
must be identified rather than silently resolved, and per CLAUDE.md 7 the
source code is the authority on what exists.

APPROVED stack (per architecture.md and rules.md):

Frontend:
React
Tailwind CSS

Backend:
FastAPI

Database:
PostgreSQL (SQLAlchemy + Alembic)

AI Runtime:
Ollama

Containerization:
Docker

ACTUAL stack in the codebase (verified by inspection 2026-09-13):

Frontend:
React 19 + Vite 7
Plain CSS (Tailwind is NOT installed)
react-router-dom 7
firebase 12.9 (client SDK)
three 0.186 + @react-three/fiber 9.8 (3D Design module only, lazy loaded)
vitest 3 + @testing-library/react + jsdom (dev, frontend tests)

Backend:
FastAPI + Uvicorn
pydantic-settings, httpx
opencv-python-headless 5.0 + numpy 2.4 (3D Design floor-plan image analysis)
pytest (dev, requirements-dev.txt)
google-genai (Gemini)
firebase-admin

Database:
Firebase Firestore
No PostgreSQL, SQLAlchemy or Alembic exists anywhere.

Authentication:
Firebase Auth REST API, called DIRECTLY from the frontend.
There is no backend authentication or authorization of any kind.

AI Runtime:
Google Gemini (model gemini-3.6-flash). Ollama is not integrated at all.

Containerization:
No Dockerfile or docker-compose.yml exists in the project.

Unresolved decision: either update the documentation to match the Firebase +
Gemini implementation, or migrate the implementation to PostgreSQL + Ollama.
This has not been decided by the user and must not be changed unilaterally.

Additional libraries must follow rules.md.

1.6 AI Architecture Decision

The project uses a centralized AI architecture.

General flow:

User
 ↓
React Chat Interface
 ↓
FastAPI
 ↓
AI Service
 ↓
Ollama
 ↓
AI Model
 ↓
Intent Detection / Routing
 ↓
Relevant Application Module
 ↓
Response
 ↓
User

The AI should not directly access the database without going through approved backend services.

1.7 Important AI Decision

The centralized chatbot is not only a general question-answering system.

It can identify supported user intents and route requests to appropriate modules.

Example:

User:
"Find me a house in Islamabad under 2 crore."

        ↓

Intent:
PROPERTY_SEARCH

        ↓

Property Service

        ↓

Filtered Properties

Another example:

User:
"Estimate the construction cost of a 5 marla house."

        ↓

Intent:
COST_ESTIMATION

        ↓

Cost Estimation Service

        ↓

Estimated Cost
1.8 AI Boundaries

AI must not:

Bypass authentication.
Bypass authorization.
Modify protected data without authorized backend operations.
Expose private user information.
Expose passwords or secrets.
Invent properties as database results.
Execute arbitrary system commands.
Make unauthorized administrative decisions.

AI-generated information must be clearly distinguished from authoritative database information.

2. What Happens

This section records major project updates, decisions, completed work, issues, and solutions.

2.1 Major Decisions
Decision 001 — Centralized AI Chatbot

Status: Approved

The project will use a centralized chatbot as the main AI interaction point.

The chatbot will be integrated with the backend and may route supported requests to application modules.

Decision 002 — Backend

Status: Approved

FastAPI will be used as the backend API framework.

The backend will handle:

Authentication
Authorization
Business logic
Database operations
AI integration
File management
Chat functionality
Validation
Decision 003 — Frontend

Status: Approved

React will be used for the frontend.

Tailwind CSS will be used for styling.

The frontend should use reusable components.

Decision 004 — Database

Status: Approved

PostgreSQL will be used as the primary relational database.

Decision 005 — Containerization

Status: Approved

Docker will be used to containerize the application and its services.

Decision 006 — Design Philosophy

Status: Approved

The UI follows:

Mobile-First
Responsive
Accessible
Component-Based
Consistent
Professional
Decision 007 — Cost Estimation

Status: Approved

Construction cost calculations should be performed using deterministic application logic.

AI may explain or assist with the result but should not replace the calculation engine.

Decision 008 — Authorization

Status: Approved

Role-Based Access Control (RBAC) will be used.

Roles:

VISITOR
USER
DEALER
ADMIN

Backend authorization is mandatory even when frontend routes are protected.

2.2 Completed Tasks

Update this section whenever a significant feature is completed.

Current initial documentation status:

[x] PRD documentation
[x] Architecture documentation
[x] Development rules documentation
[x] Development phase documentation
[x] UI/UX design documentation
[x] Memory documentation

Application implementation status (verified 2026-09-16):

[~] Authentication          Firebase Auth via frontend only; NO backend auth
[~] User registration       Signup.jsx calls Firebase Auth REST directly
[~] User login              same as above
[~] Logout                  frontend state only
[ ] Password reset
[ ] RBAC                    no roles enforced anywhere in the backend
[~] User dashboard          UI shell exists, Firestore-backed
[~] Dealer dashboard        UI shell only (DealerDashboard.jsx)
[~] Admin dashboard         UI shell only, NOT protected by any backend check
[~] Property CRUD           frontend reads Firestore directly; no backend API
[~] Property search         client-side over Firestore
[ ] Property filtering      partial/client-side
[ ] Property sorting
[ ] Property recommendation chatbot module returns MOCK data
[x] Centralized AI chatbot  working, Gemini-backed (see UPDATE-001)
[x] AI intent detection     keyword/regex router, not an ML classifier
[x] AI request routing      routes to 5 module keys
[ ] 2D design               BUILT then REMOVED on user request (UPDATE-002)
[x] 3D design               BUILT and tested (UPDATE-004, UPDATE-010: 2D image
                            -> 3D, GLB, React Three Fiber viewer)
[x] Interior design         photo -> editable room editor BUILT and tested
                            (UPDATE-011); the chatbot's interior_design
                            intent still returns MOCK data
[ ] Cost estimation         UI page only; chatbot module returns MOCK data
[ ] User-dealer chat        Chat.jsx exists; no backend chat API
[ ] File upload
[ ] File download
[ ] Notifications
[ ] Settings
[~] Testing                 3D + Interior Design only: pytest (139) + Vitest (62)
[ ] Docker deployment       no Docker configuration exists

Legend: [x] done  [~] partial / not per documented architecture  [ ] not started

Note: the project is NOT following phase.doc.md order. Phase 4 AI features
(chatbot, 3D design) are built while Phase 1 authentication does not exist.

The checklist must be updated as implementation progresses.

2.3 Issue Log

Record important development issues here.

Format:

Issue ID:
Date:
Module:
Problem:
Cause:
Solution:
Status:

Only record issues that are useful for future development.

Do not record trivial temporary errors.

--- RECORDED ISSUES ---

Issue ID: ISSUE-001
Date: 2026-09-14
Module: Development environment
Problem: New backend routes returned 404 and code changes appeared to have no
effect. Reported twice (2D module, then 3D module) and wrongly looked like a
code bug both times.
Cause: FIVE copies of this project exist on the D: drive:
  D:\Docker\...            (old, March, contains unrelated "Naive Bayes" code)
  D:\FYP Website\...       (old, March)
  D:\New\FYP Website\...   <-- THE LIVE ONE, all current work is here
  D:\New folder (2)\...    (old, March)
  D:\OLama\...             (old, March, contains "Naive Bayes" code)
The backend terminal was running from one of the March copies, so it served
old code, ignored file edits, and its --reload watcher watched the wrong folder.
Solution: Always start both servers from D:\New\FYP Website. Verify on startup
that uvicorn prints: Will watch for changes in these directories:
['D:\\New\\FYP Website\\haven-ai-backend'].
Status: Diagnosed. The stale copies still exist and remain a trap.
Recurrence 2026-09-16: SIX servers were listening on 127.0.0.1:8000 at once
(Windows allows duplicate binds). Five were orphaned uvicorn workers from
August started from the old copies ("Naive Bayes" chatbot), one from 9/13.
Requests hit an old one, so /api/design/3d/generate returned 404. Fixed by
killing all of them. Before starting the backend, check for leftovers with:
  netstat -ano | findstr :8000
and stop every listed PID. The code itself imports and runs correctly.

Issue ID: ISSUE-002
Date: 2026-09-13
Module: Backend / Python
Problem: A freshly started server exposed only the old routes even though
main.py on disk was correct.
Cause: Stale __pycache__ bytecode was loaded instead of the newer source;
Windows timestamp precision prevented Python from detecting the change.
Solution: Delete all __pycache__ folders under app/ and restart.
Status: Resolved.

Issue ID: ISSUE-003
Date: 2026-09-13
Module: Centralized AI Chatbot
Problem: Every Gemini call silently failed; users only ever saw the static
template fallback.
Cause: GEMINI_MODEL defaulted to gemini-2.0-flash, which Google has retired
(404 NOT_FOUND). gemini-2.5-flash is also unavailable to new keys.
Solution: Default changed to gemini-3.6-flash. Overridable via the GEMINI_MODEL
environment variable.
Status: Resolved.

Issue ID: ISSUE-004
Date: 2026-09-13
Module: Centralized AI Chatbot
Problem: The chatbot could not follow up; every turn was answered in isolation.
Cause: conversation_history was accepted by the endpoint and passed through the
orchestrator but never actually included in the Gemini request.
Solution: Added _build_gemini_contents(), which maps the frontend's
{role, content} history into Gemini's multi-turn contents (assistant -> model)
and includes the last 6 messages.
Status: Resolved and verified (bot recalled a name and city across turns).

Issue ID: ISSUE-005
Date: 2026-09-13
Module: Design modules (own implementation bug)
Problem: An area-based feasibility check could approve a layout that the
geometric packer then could not actually place, silently dropping a room while
still reporting the design as feasible.
Cause: Room areas summed to less than the available area, but 2D packing cannot
achieve 100% efficiency.
Solution (lesson for any future layout work): never trust an area estimate as
feasibility. Let the packer itself decide, and hard-fail if any requested room
is not placed. The 3D module's planner is exact for this reason.
Status: Resolved.

Issue ID: ISSUE-006
Date: 2026-09-16
Module: Security (OPEN - not fixed)
Problem: Several security defects exist in the current implementation.
  - firebase-credentials.json (a Firebase Admin service account) is stored
    inside haven-ai-backend/ and would be committed if git is initialised.
  - The Firebase web API key is hardcoded in haven-ai-react/src/firebase.js.
  - No backend endpoint performs any authentication or authorization.
  - /api/chat/send accepts any caller-supplied user_id with no verification.
  - AdminDashboard and DealerDashboard are protected by frontend routing only,
    which rules.md 7.5 and architecture.md 1.16 explicitly forbid.
Cause: Firebase-first prototyping; backend auth was never built.
Solution: Not yet applied. Requires Phase 1 authentication work.
Status: OPEN.

2.4 Known Limitations

Known limitations should be documented here.
Remove limitations when they are resolved.

Architecture / stack:
[ ] No backend authentication or authorization exists at all.
[ ] React connects directly to Firestore and Firebase Auth, which violates
    architecture.md Rule 1/Rule 3 and rules.md 2.4/2.5.
[ ] PostgreSQL, SQLAlchemy, Alembic and Ollama are documented but not built.
[ ] Tailwind CSS is documented but not installed; styling is plain CSS.
[ ] No Docker configuration exists.
[ ] The project is not under git version control.
[~] Automated tests exist only for the 3D Design and Interior Design modules.
[ ] Signed-in sessions keep only the Firebase ID token (localStorage
    housing_user, written by Signup.jsx), not the refresh token, so backend
    calls that need sign-in (saving interior designs) fail with "sign-in has
    expired" one hour after login until the user logs in again.

AI modules:
[ ] Intent detection is keyword/regex based, not machine learning.
[ ] Property recommendation returns MOCK data (or a simple Firestore substring
    match); there is no ranking model.
[ ] Construction cost estimation returns MOCK data; no calculation engine.
[ ] The chatbot's interior_design intent returns MOCK data (the Interior
    Design page itself is real, UPDATE-011).
[ ] 2D design module was built and then removed; the chatbot's design_2d
    intent again returns placeholder mock data.

3D Design module (built, working):
[ ] Maximum of 2 storeys by design.
[ ] Setbacks and room minimums are generic Pakistani planning conventions,
    clearly labelled as assumptions. They are NOT any society's real bylaws.
[ ] Save/Load uses browser localStorage only; real per-user persistence needs
    Phase 1 authentication.
[ ] The stairwell occupies the same corner on both floors but its depth can
    differ between them, so the flights are not perfectly aligned. Fixing this
    properly needs a reserved fixed-size circulation core.
[ ] Layout is a conceptual massing model, not a construction drawing. There is
    no door-swing or adjacency logic (e.g. kitchen next to dining). Furniture
    in the GLB is indicative only (UPDATE-010).
[ ] Floor-plan image analysis (UPDATE-010) does not read text: room names and
    printed dimensions are not OCR'd. The user must give the overall width
    and/or depth (outside wall to outside wall); room types come only from
    HAVEN's colour legend, stair hatching, or the user's review.
[ ] One uploaded image = one floor. Two-floor models from images only work
    for PNGs exported by HAVEN's 2D page (plan data embedded in the file).
[ ] Openings wider than 5 ft are not bridged, so an open-plan lounge/dining
    joined by a wide arch is read as one room. Curved or diagonal walls are
    not supported (rooms are split into axis-aligned rectangles).
[ ] Measured accuracy: within ~0.35 ft on clean synthetic plans at 20 px/ft,
    within ~0.6 ft (about one wall stroke) on HAVEN-style drawings at 16 px/ft.
    Not validated on scanned or hand-drawn plans.
[ ] Generated GLBs are kept in backend memory for 2 hours (max 64); after a
    restart or expiry the viewer asks the user to generate again.

Interior Design module (built, working - UPDATE-011):
[ ] Detection is semantic segmentation (SegFormer-B2/ADE20K): touching pieces
    of the same kind (two chairs side by side) can come out as one object;
    thin parts (lamp poles, chair legs) are sometimes missed or labelled as
    wall. Materials of photo objects are not measured, only assumed by type.
[ ] Sizes/depth come from an assumed level camera (65 deg FOV) scaled by
    typical furniture sizes; approximate, and cruder when the photo has no
    receding floor lines.
[ ] Photo objects are 2D cut-outs: they can move, scale and be mirrored but
    not turned; parts hidden in the photo stay missing when moved. Swapping
    in a 3D model allows real rotation. Added/replacement furniture is a
    simple parametric 3D model (boxy look); the optional Gemini photoreal
    pass is what makes the final image photographic, and it needs billing.
[ ] Model weights are NVIDIA's SegFormer (non-commercial licence).
[ ] Uploaded rooms are stored on the backend disk (storage/interior); a saved
    design reopens only on the server that holds its folder.

2.5 Change Log

Actual recorded updates, newest last. Format per 4.3 of this document.

## UPDATE-001

Date: 2026-09-13
Phase: Phase 4 (out of documented order)
Module: Centralized AI Chatbot

Change:
Made the existing Gemini-backed chatbot actually work. Three fixes in
app/services/CentralizedChatbot.py:
  1. GEMINI_MODEL default changed from the retired gemini-2.0-flash to
     gemini-3.6-flash (see ISSUE-003).
  2. Added _build_gemini_contents() so conversation history reaches the model
     (see ISSUE-004).
  3. Added explicit 429 / RESOURCE_EXHAUSTED handling, and extracted
     _template_response() so the rate-limited path and the
     Gemini-unavailable path share one deterministic fallback.

Reason:
The chatbot silently degraded to static templates on every request and had no
multi-turn memory.

Impact:
Live Gemini responses now work; follow-up questions resolve against earlier
turns; missing API key, API failure and rate limits all degrade gracefully.
The API key stays server-side only and is never exposed to the frontend.

Status: Completed and tested.
Next Step: None outstanding for this module.

## UPDATE-002

Date: 2026-09-13
Phase: Phase 4
Module: 2D Design

Change:
A full deterministic 2D floor-plan module was implemented (requirement
extraction, configurable society rules, constraint engine, layout generator,
validator, REST endpoint, React SVG renderer, chatbot wiring), then REMOVED
in its entirety on the user's explicit instruction.

Reason:
User requested removal. No defect was reported; the module was tested and
working when deleted.

Impact:
All 2D module files deleted and every edit to existing files reverted. The
chatbot's design_2d intent again returns placeholder mock data. Verified that
the backend exposes only the original routes and the frontend still builds.

Status: Reverted. Do not reinstate without being asked.
Next Step: None.

## UPDATE-003

Date: 2026-09-13
Phase: Maintenance
Module: Centralized AI Chatbot

Change:
Fixed three Pylance type errors in CentralizedChatbot.py:
  - added `db is None` guards in save_to_firebase and
    _fetch_real_properties_sync (reportOptionalMemberAccess)
  - conversation_history typed Optional[list] instead of list = None
  - annotated db as Optional[firestore.Client]

Reason: Static type errors reported in the editor.
Impact: No behaviour change; the None guards also make the code more defensive.
Status: Completed.
Next Step: None.

## UPDATE-004

Date: 2026-09-13 / 2026-09-16
Phase: Phase 4
Module: 3D Design

Change:
Replaced the fake 3D page (a hand-drawn 2D canvas isometric demo with four
hardcoded shapes) with a real generate-from-requirements 3D module.

New backend package app/services/design3d/:
  requirements.py   regex extraction of plot size, storeys and room counts
  layout.py         deterministic space planning and exact feasibility
  model_builder.py  extrudes the plan into walls, openings, slabs, roof, stairs
  service.py        pipeline orchestration and geometry validation
New endpoint app/api/endpoints/design_3d.py -> POST /api/design/3d/generate
Registered in app/main.py.
CentralizedChatbot design_3d intent now calls this engine in-process instead
of returning mock data, and its response template was rewritten to match.

New frontend:
  src/components/ThreeDViewer.jsx   Three.js renderer, lazy loaded
  src/pages/ThreeDDesign.jsx        rewritten: brief form, toolbar, viewport,
                                    properties panel (per design.md 18.2)
  src/api.js                        added api.design3d.generate

Dependency added: three@0.186.0. User explicitly approved this; rules.md 6.28
requires that approval. Lazy loaded so the main bundle stayed at 728 kB and
Three.js sits in a separate 548 kB chunk only this page loads.

Reason:
The 3D module was required by PRD 3.6, architecture.md 1.14 and phase.doc.md
5.7, and the existing page was a non-functional visual demo.

Impact:
Users can describe a plot and requirements and get a validated, structured,
explorable 3D model. All geometry is computed by deterministic Python (no
image generation and no LLM involvement in the geometry), satisfying
rules.md 5.3. Feasibility is exact: the packer itself decides what fits.

Design decisions worth remembering:
  - Rooms are packed into full-width bands stretched to tile the plan, so
    partition walls stay collinear and wall de-duplication is exact.
  - Floors are allocated by purpose (shared space and one WC downstairs,
    bedrooms upstairs), not by whatever fits first.
  - Stretching is capped; leftover width becomes a corridor/open hall and
    leftover depth becomes a terrace (top floor) or family hall (lower floor).
  - The building takes only the depth it needs; the rest of the plot is garden.
  - A car porch is deliberately left unwalled; a top-floor terrace keeps only
    a parapet and the roof slab stops short of it.
  - Hard cap of 2 storeys; "triple storey" clamps rather than erroring.

Status: Completed and tested. 13 backend cases (5/10 marla, explicit and
marla-derived dimensions, single/double/auto storeys, over-capacity, invalid,
missing and ambiguous input, no rooms, form overrides, storey clamping) all
correct, with geometry validated for overlaps, bounds and openings. REST error
paths verified including 422 on empty prompt. Chatbot routing verified with no
regression to property/cost/2D/interior/general intents. A Three.js
scene-construction smoke test ran five display variants (135 boxes) with no
runtime errors. Frontend builds and lints clean.

Next Step: User to verify in the browser after starting the servers from the
correct folder (see ISSUE-001).

## UPDATE-005

Date: 2026-09-27
Phase: Phase 4
Module: 2D Design

Change:
2D Design module reinstated on the user's explicit request, this time
LLM-generated: the user supplied a full "2D House Design Generation" system
prompt and chose to use it with Gemini rather than a deterministic planner.

Backend (app/services/design2d/):
  prompt.py     the user's prompt verbatim + an appended output contract
                (coordinate convention, field names, marla table taken from
                design3d MARLA_TYPICAL_DIMS_FT)
  validator.py  deterministic checks: plot area recomputed, rectangles inside
                plot, no overlaps, floors vs status, staircase on both floors,
                room counts vs extracted requirements, parking, min sizes,
                door/window fit
  service.py    Gemini JSON mode, one repair round-trip with validator errors,
                model fallback list (GEMINI_MODELS_2D env, default
                GEMINI_MODEL, gemini-3.8-flash, gemini-flash-latest)
Endpoint app/api/endpoints/design_2d.py -> POST /api/design/2d/generate
CentralizedChatbot design_2d intent now calls generate_2d_plan in-process.

Frontend: src/components/FloorPlanViewer.jsx (SVG, viewBox in feet),
FloorPlanGenerator.jsx, floorPlanColors.js, api.design2d.generate; generator
section added to src/pages/TwoDDesign.jsx (existing AIChat kept).

Reason: User request.

Impact:
Deliberate exception to rules.md 5.3: geometry comes from the LLM. The
validator's result is returned as `validation` and failed checks are shown
to the user, so an invalid layout is never presented as valid.

Status: Completed. Live-tested: 25x50 4-bed request -> valid two-floor plan
(first attempt), missing plot -> INSUFFICIENT_INFORMATION, oversized brief ->
NOT_FEASIBLE; SVG render checked visually; 422/503 paths verified; frontend
lints and builds. Further live tests blocked by Gemini free-tier quota
(20 requests/day per model) and 503 overload.
Next Step: User to test in the browser once the Gemini quota resets.

## UPDATE-006

Date: 2026-09-27
Phase: Phase 4
Module: 2D Design -> 3D Design

Change:
A generated 2D floor plan can be sent to the 3D Design page and built as a
3D model with the exact same room positions, doors and windows.

Backend:
  app/services/design3d/from_plan2d.py  deterministic converter. Walls are
      built by cutting every wall line at all room corners and classifying
      each segment by the items on either side (enclosed room / corridor /
      car porch / open-air space), so arbitrary rectangles de-duplicate
      correctly. Per-room slabs, roof pieces (ground-floor parts not covered
      by the first floor get their own lower roof), parapets on first-floor
      terraces, stairs from the staircase rectangle. The plan is re-validated
      with design2d/validator.py before converting.
  POST /api/design/3d/from-2d  (app/api/endpoints/design_3d.py)
Frontend:
  FloorPlanGenerator.jsx  "View in 3D" button -> navigate('/3d-design',
      { state: { plan2d } })
  ThreeDDesign.jsx        builds the model from router state on arrival,
      banner with a link back to 2D Design
  ThreeDViewer.jsx        supports storey.slabs[], roof.pieces[] and several
      openings per wall (existing generated models render unchanged)
  api.js                  api.design3d.fromPlan2d

Reason: User request.
Status: Completed. Converter tested on a live two-floor plan; endpoint
tested for valid, NOT_FEASIBLE, invalid-geometry and malformed input;
Three.js render checked visually in headless Chrome; frontend lints/builds.
Next Step: User to test the round trip in the browser.

## UPDATE-007

Date: 2026-09-27
Phase: Phase 4
Module: 3D Design (image-based input)

Change:
The 3D Design module accepts an optional photo of the user's existing
property alongside the text brief and plot details.

Backend:
  app/services/gemini.py              shared Gemini client + retry/fallback
                                      (2D service refactored onto it)
  design3d/reference_prompt.py        vision prompt: observed vs not
                                      determinable, no dimensions, structural
                                      requests flagged, clarifications
  design3d/reference.py               pipeline: content-sniffed upload
                                      (JPEG/PNG/WebP, 8 MB, in memory only,
                                      never written to disk), missing plot
                                      size asked BEFORE any Gemini call,
                                      vision analysis, clarification gate,
                                      deterministic model (room planner if
                                      rooms requested, else exterior shell),
                                      optional photoreal render
  design3d/facade.py                  front doors/windows/garage door fitted
                                      into free front-wall space (falls back
                                      to smaller windows), cantilevered
                                      balconies, appearance colours/cladding
  POST /api/design/3d/generate-from-image  (multipart; 415 bad file,
                                      503 quota, NEEDS_CLARIFICATION status)
  config.py: GEMINI_VISION_MODELS, GEMINI_IMAGE_MODELS
Frontend:
  ThreeDDesign.jsx      photo picker + preview, render checkbox,
                        clarification questions
  ReferenceAnalysis.jsx observed / not determinable / requested / kept /
                        proposed finish / render panels
  ThreeDViewer.jsx      appearance colours, procedural cladding textures
                        (stone, brick, wood, tile, concrete, glass), window
                        frames, balconies with glass or solid railings,
                        front camera for photo-based models; scene mirrored
                        on x so left/right match the plans and photos (this
                        was mirrored for every 3D model before)

Reason: User supplied a full requirement for image + text 3D design.

Impact:
Photorealistic rendering uses Gemini image models, which have 0 free-tier
quota; it reports "needs billing" instead of failing. The 3D geometry stays
deterministic (rules.md 5.3); Gemini only describes the photo.

Status: Completed. Live test with a synthetic two-storey facade photo and the
spec's example prompt: correct observations, FEASIBLE model, render reported
unavailable. Upload validation (wrong type by content, >8 MB, missing file,
bad storeys), missing dimensions and text mode verified. 3D output checked
visually. Frontend lints and builds.
Next Step: User to test with a real property photo in the browser.

## UPDATE-008

Date: 2026-09-27
Phase: Phase 4
Module: 3D Design

Change:
On the user's instruction ("don't use Gemini for now, use a built-in
model"), the 3D Design module no longer calls Gemini anywhere.

  design3d/photo_analyzer.py      built-in photo analysis in plain Python on a
                                  small RGB grid (max 128 px) that the browser
                                  decodes and sends (src/photoPixels.js):
                                  quality (exposure, contrast, sharpness) and
                                  colour palette via deterministic k-means.
                                  No new dependency (rules.md 6.28).
  design3d/modification_parser.py rule-based reading of the requested changes:
                                  style presets, colour words, cladding,
                                  window style, balconies, garage, "keep
                                  structure"; structural requests (add storey,
                                  move walls, extensions) and unrecognised
                                  requests become blocking clarifications
  design3d/reference.py           DESIGN3D_PHOTO_ANALYZER setting, default
                                  "builtin"; "gemini" restores the Gemini
                                  vision path (kept, not deleted, because the
                                  user said "for now"). Render only with gemini.
  Floors come from the storeys field (asked if missing); front windows per
  floor, garage door and existing balcony from new form fields.
  CentralizedChatbot: design_3d chat replies use the template, not Gemini.
  Frontend: render checkbox removed; photo facts fields added.

Status: Completed. End-to-end tests with pixels produced by the real browser
code and Gemini patched to raise: spec example FEASIBLE (wall colour measured
exactly), missing storeys, structural request, unrecognised request, bad
pixel data (415), dark photo, photo-only, keep-colours cases all correct.
Frontend lints and builds.
Next Step: User to test in the browser. Switch back with
DESIGN3D_PHOTO_ANALYZER=gemini in .env.

## UPDATE-009

Date: 2026-09-28
Phase: Phase 4
Module: 2D Design

Change:
Generated floor plans can be downloaded (phase.doc.md 5.12 File Download).
  src/components/floorPlanExport.js  PNG sheet (title, plot/floor summary,
      one or more floors side by side, not-an-approved-drawing disclaimer,
      16 px per ft) and standalone vector SVG, built in the browser
  FloorPlanGenerator.jsx  buttons: PNG (current floor), PNG (all floors, only
      for two-floor plans), SVG (current floor); exports use off-screen,
      unselected copies of each floor so a highlighted room is never saved
Files are named floor-plan-<W>x<L>ft-<floor>.png/.svg.

Reason: User request.
Status: Completed. PNG (both floors) and SVG outputs rendered and checked
visually in headless Chrome; frontend lints and builds.
Next Step: None.

## UPDATE-010

Date: 2026-09-28
Phase: Phase 4
Module: 3D Design (2D design -> 3D visualization)

Change:
Implemented the user's "2D Design -> 3D Visualization Module" specification
as three separated layers on top of the existing 3D module.

Layer 1 - AI/CV (new package app/services/plan_vision/):
  image_io.py      content-sniffed PNG/JPEG/WebP, 8 MB, 40 MP decode cap,
                   in memory only; reads a HAVEN plan embedded in a PNG
                   (iTXt chunk "haven-plan2d") and re-validates it
  segmentation.py  classical OpenCV: stroke-thickness histogram -> wall
                   mask, gap bridging for doors/windows, enclosed rooms,
                   L-shapes split into rectangles, stair hatching, fills
  structure.py     pixels -> feet from the user's dimensions, wall-centreline
                   snapping, output in the 2D module's plan schema with
                   detection provenance; types from HAVEN's colour legend
  service.py       statuses ANALYZED / NEEDS_DIMENSIONS / DIMENSION_MISMATCH /
                   LOW_RESOLUTION / NOT_A_FLOOR_PLAN, confidence scores,
                   detected / explicit / inferred / missing lists
  Model choice: classical CV, not a neural model or Gemini (the user earlier
  asked for no Gemini in the 3D module). Deterministic, CPU-only, no model
  download; it fails visibly instead of inventing a layout. No OCR.
Layer 2 - geometry:
  design3d/arch_defaults.py  single home for units, axes and architectural
                             defaults (model_builder re-exports them)
  design3d/from_plan2d.py    supports multi-rectangle rooms (`group`) and
                             measured wall thickness (`structure`)
  design3d/gltf_export.py    dependency-free GLB writer: named nodes per
                             storey/layer, one pickable node per room with
                             extras, PBR materials, metres, +Y up, road at +Z
  design3d/furniture.py      indicative furniture, clear of door swings
  design3d/model_store.py    GLBs held in memory by random id (2 h, 64 max)
  model_builder.py FIX       overlapping collinear walls are merged; before,
                             a solid wall could cover another wall's door
                             (blocked doorways in text-generated models)
Endpoints (app/api/endpoints/design_3d.py):
  POST /api/design/3d/analyze            image -> structured plan (Layer 1)
  POST /api/design/3d/from-2d            also accepts analysed plans
  GET  /api/design/3d/models/{id}.glb    serves a generated GLB
  /generate, /from-2d, /generate-from-image responses gain `glb`
  (model_url, format, metadata). OpenCV is imported lazily, so a missing
  install disables only /analyze (503), not the other 3D endpoints.
Layer 3 - React Three Fiber (src/components/threeD/):
  ThreeDViewer.jsx    loads the GLB; studio lighting, shadows, orbit / zoom /
                      pan, animated views (exterior, interior look-around,
                      top, front, side, fit, reset), room picking and
                      highlight, error boundary, WebGL check, loading /
                      expired / failed states
  ModelToolbar.jsx    walls, roof, see-through, doors, windows, furniture,
                      floor filter, views
  PlanImageImport.jsx upload -> "Analyzing your floor plan..." -> review
                      (rename / retype rooms, confidence, provenance) ->
                      "Generating 3D model..."
  viewerUtils.js, houseLoader.js, cladding.js, planReview.js
  The old imperative components/ThreeDViewer.jsx was replaced; all of its
  features, including photo cladding, were carried over.
  ThreeDDesign.jsx: tabs "Describe requirements" (unchanged form), "Upload
  2D design", "Use existing 2D design" (latest plan from the 2D page).
2D module integration: FloorPlanGenerator saves the latest plan
(localStorage haven.design2d.lastPlan); PNG downloads embed the plan JSON so
re-uploading one is read exactly.
Dependencies added (the spec named R3F and OpenCV): @react-three/fiber,
opencv-python-headless, numpy; dev: pytest, vitest, @testing-library/react,
@testing-library/jest-dom, jsdom. Rules 6.28: needed for the specified R3F
viewer and image analysis; three already existed; all maintained; no
secrets; OpenCV isolated behind a lazy import.

Reason: User supplied the full module specification.

Status: Completed and tested.
  Backend: 47 pytest tests (tests/): ground-truth synthetic plans (rooms,
  doors, windows, thickness, rotation, JPEG, L-shape, legend, stairs,
  embedded/tampered PNG, invalid/low-res/non-plan images), geometry, GLB
  units/structure, API.
  Frontend: 30 Vitest tests, including parsing real backend GLBs.
  Browser (headless Chrome against the real servers): text brief, existing
  2D design (two floors), HAVEN-style image, embedded PNG, generic plan,
  non-plan image, missing dimensions, orbit/zoom, views, toggles, room click
  and list selection verified with screenshots; no console errors. Other
  pages (/, /2d-design, /interior-design, /cost-estimation, /properties)
  load without errors.
  Run: backend  venv\Scripts\python -m pytest
       frontend npm test
Note: this network downloads from PyPI very slowly on a single connection;
the OpenCV wheel was fetched in parallel ranges and its SHA-256 checked
against PyPI before installing.
Next Step: User to try the Upload tab with their own floor-plan images.

## UPDATE-011

Date: 2026-09-30
Phase: Phase 4
Module: Interior Design

Change:
Replaced the chat-only Interior Design page with an interactive room editor
(user supplied the full module specification). Decisions made with the user:
local segmentation model (not Gemini), Firestore for saved designs, composite
render always + optional Gemini photoreal pass.

  Layer 1  app/services/interior/segmentation.py  SegFormer-B2 (ADE20K, ONNX,
           onnxruntime CPU, ~2 s) in ml_models/segformer-b2-ade/
           image_input.py  content-sniffed JPG/PNG/WebP, 10 MB, >=320 px,
           dark/washed-out/blurry rejection
           scene_builder.py  walls (split at corners), floor, ceiling, object
           instances with ids (sofa_001...), GrabCut-refined soft masks, leg
           recovery, placement (floor/wall/ceiling/surface/fixed), relations
           (stands_on/hangs_on/on/in_front_of), room layout (wall/floor seam)
           camera.py  vanishing point -> horizon; ground-plane metric model,
           scale calibrated from typical furniture widths
  Layer 2  operations.py  scene JSON + explicit validated operations
           (update_object, update_surface, transform_object, replace_object,
           add_object, remove_object, restore_object, reset_object);
           geometry.py  perspective moves, floor/wall/ceiling constraints,
           scale limits+warnings, 3D model projection; furniture3d.py
           parametric models; store.py  disk store: original, masks,
           detections, every version (undo/redo/reset), op log
  Layer 3  renderer.py  composite: clean plate (per-surface inpainting + row
           texture copy), lighting-preserving recolour/materials
           (materials.py, textures in floor-plane metres), cut-outs with
           contact shadows, 3D models; photoreal.py optional Gemini pass;
           designs.py  Firestore interior_designs (backend-only writes)
  API      app/api/endpoints/interior.py  /api/interior/... (scenes,
           operations, undo/redo/reset, render, sprite, final, catalog,
           designs); app/core/auth.py verifies Firebase ID tokens,
           app/core/firebase.py shares the Admin app
  Frontend src/components/interior/ (RoomUpload, RoomEditor, EditorStage,
           PropertiesPanel, SavedDesigns, editorMath, uploadCheck),
           pages/InteriorDesign.jsx (AI ideas chat kept below the editor),
           api.js interior client, index.css .ie-* styles
  Fix      App.jsx: the 320 px sidebar margin now applies only where the
           sidebar is shown (>1100 px); every page was squeezed on phones.
Dependencies added: onnxruntime (backend). Dev-only, not in the project:
puppeteer-core in the session scratchpad for browser checks.

Status: Completed and tested.
  Backend: 99 pytest tests pass (52 new: upload validation, operations,
  constraints, history, conflicts, save/reload/ownership, render position/
  size/colour/material/localisation, real-model detection on 3 photos).
  Frontend: 51 Vitest tests pass (21 new). Build OK; new files lint clean.
  Browser (headless Chrome, real servers): desktop and phone (touch) upload,
  analyse, select, drag, recolour, floor material, add, undo, final image;
  no console errors, no horizontal scroll on phones. Firestore write/read/
  list/delete checked live with a throwaway record (deleted).
Next Step: User to try it with their own room photos; enable Gemini billing
if the photoreal pass is wanted.

## UPDATE-012

Date: 2026-09-30
Phase: Phase 4
Module: Interior Design - object library

Change:
Data-driven object library replacing the fixed "replace with" list (user
specification sections 12-33).
  library_data/categories.json + items/*.json   167 items, 38 categories in
      8 groups (seating, tables, bedroom, living & storage, lighting,
      decoration, curtains & blinds, rugs); each item = generator + params +
      nominal dimensions (marked "typical", not measured) + style, material,
      colour variants. Flooring/wall finishes are the material library
      (new: porcelain, vinyl planks, walnut parquet, slate, rattan).
  library.py      load/validate, server-side search: filters, facets per
                  category, sort, pagination, rule-based natural-language
                  interpretation (only returns existing items; reports
                  relaxed filters). Kinds: parametric, image (2D cut-out
                  assets), gltf reserved.
  furniture3d.py  rewritten: parametric generators (sofa incl. 2/3/4-seat,
                  L/U, recliner, arm/leg/back styles; chairs; tables; storage;
                  beds; lamps; pendants; chandeliers; ceiling lights; plants;
                  vases; decor; TV; rugs)
  wall2d.py       art (5 styles, sets), mirrors (rect/round/arch/oval),
                  clocks, curtains (simple/blackout/sheer/grommet/
                  traditional), blinds, wall lights
  geometry.py     ceiling fixtures hang from an estimated ceiling plane;
                  table-top items rest on the furniture beneath (support
                  depth); image assets; free-spot placement per placement
  thumbnails.py   previews rendered by the room renderer, disk+memory cache,
                  background warm-up; material swatches
  operations.py   replace_object/add_object take library_item (legacy type
                  still accepted); replacement gets a NEW id, keeps
                  position (and turn when both can turn), uses the item's
                  real size, old object kept in `removed`; reset on the new
                  piece restores the original; children re-parented
  API             /api/interior/library/categories|search|items/{id}|
                  items/{id}/thumbnail.png|materials/{key}/swatch.png
  Frontend        ObjectLibrary.jsx (categories, search, facet filters,
                  sort, load more, lazy previews, colour variants),
                  "Change <object>" in the properties panel, library-based
                  Add, material swatch grids; index.css .ol-* styles
Status: Completed and tested. Backend 121 pytest (22 new library tests incl.
  data-only extension, bad data rejection, 2D asset rendering); frontend
  56 Vitest; lint clean; build OK; browser-checked desktop + phone
  (open library from sofa, NL search, replace, rotate, recolour, add
  pendant, undo), no console errors.
Known limits: models are simple parametric solids (the optional Gemini
  photoreal pass is what makes them photographic); ceiling height is
  assumed 2.6 m unless the ceiling line is visible; no GLB loader yet.
Next Step: User evaluation; add real product assets (image/gltf) as needed.

## UPDATE-013

Date: 2026-10-01
Phase: Phase 4
Module: Interior Design - photorealistic real-world objects

Change:
Real 3D furniture and photographed materials instead of simple solids
(user specification "PHOTOREALISTIC REAL-WORLD OBJECT REQUIREMENT").
  Assets          107 real 3D models (furniture, lighting, plants, vases,
                  decor, mirrors, frames, clocks) + 18 PBR texture sets,
                  all CC0 from Poly Haven; scripts/fetch_interior_assets.py
                  (MD5-checked; 1k standard, --high adds 2k); stored in
                  INTERIOR_ASSET_DIR (assets/interior, ~880 MB with 2k)
  meshes.py       glTF 2.0 loader (nodes, accessors, PBR materials),
                  normalised to real metres, front towards the camera,
                  unit fix from the publisher's measured size, cached
                  index (size, colour, materials)
  raster.py       vectorised scan-line rasteriser with z-buffer (numpy)
  mesh_render.py  PBR shading (GGX, normal/roughness/metal/AO maps, mips),
                  room reflections, glass/blend, alpha-tested leaves,
                  self-shadow + cast shadow on floor/walls (shadow map),
                  contact occlusion, upholstery recolour (named material or
                  colour mask) and material change (tri-planar at real scale)
  lighting.py     room light from the photo: window/lamp or overhead key
                  toward the brighter side, sky/ground bounce, exposure and
                  white balance calibrated on the walls
  pbr.py + library_data/pbr_materials.json  roughness/metal/opacity for
                  every material; photographed textures at real size for
                  floors, walls and fabrics (new: cotton, MDF, granite,
                  stone, stainless steel, plastic)
  library         kind "mesh" items (items/scanned.json): measured size,
                  "Real 3D model" badge, realism facet/filter, real models
                  ranked first and used as category defaults
  geometry        wall-mounted 3D models, mesh outlines for selection,
                  companion placement (coffee table in front of the sofa,
                  side table/plant/lamp beside it, no collisions)
  renderer        clean plate: legs/contact shadow of removed pieces
                  erased, floor refilled along its own lines (planks stay
                  straight), skirting continued; final render uses 2k assets
Status: Completed and tested. Backend 133 pytest (12 new realism tests);
  frontend 57 Vitest; lint clean; browser-checked (replace sofa with a
  real model from NL search, rotate, recolour, add a plant, undo).
Known limits: CPU renderer, 1-3 s per changed real model; pieces without
  recolourable upholstery keep their real finish; no floor lamp, curtain,
  rug, bed-linen or TV models in the CC0 set yet (those stay procedural);
  shadows cast by removed photo furniture onto walls stay in the photo;
  lighting is estimated, not measured.
Next Step: User evaluation; add more CC0/licensed models to items/*.json.

## UPDATE-014

Date: 2026-10-01
Phase: Phase 4
Module: Interior Design - exact object replacement and size matching

Change:
Replacing an object keeps its size, place and turn (user specification
"EXACT OBJECT REPLACEMENT AND SIZE MATCHING"); before, the library piece
came in at its catalogue size.
  fit.py          scale from the catalogue (real) size to fill the old
                  object's space. Photo object: matched on its outline in
                  the picture through the same camera (iterated, so the
                  physical size follows from perspective), outline lined up
                  (centre across; bottom / centre / top for floor / wall /
                  ceiling). 3D object: matched on its size in metres.
                  Uniform scale on the dominant dimension (width of a sofa,
                  height of a wardrobe); tall floor pieces may be nudged
                  <=15% in width; rugs/curtains/blinds fit width and
                  length/drop independently; sides cut off by the photo
                  edge are ignored (both cut -> catalogue size); real
                  pieces stay within 0.5x-2x of their real size; a floor
                  piece that would go through the wall is made up to 15%
                  shallower before it is moved forward (then re-fitted)
  operations.py   replace_object: changes.fit "match" (default) or
                  "catalogue"; record kept on the object as `fit`
                  (mode, basis, scale, catalogue size, target); turn kept
                  for wall tilt too; position from the matching point of
                  the old outline (ceiling: top, table: base).
                  New operation fit_object {size: original | catalogue}
  geometry.py     mesh outlines use every vertex (convex hull); photo floor
                  objects get an estimated depth (category's typical ratio)
  library.py      summary adds default_scale and model_reference
  frontend        Size panel: "Sized to fill the space of the original
                  sofa", catalogue size, buttons "Match original size" /
                  "Use catalogue size"; library dialog explains the fit
Status: Completed and tested. Backend 139 pytest (6 new in
  tests/test_interior_replace_fit.py, 2 replace tests updated); frontend
  59 Vitest (PropertiesPanel.test.jsx new); build OK.
Known limits: the turn of a piece in the photo is not measured (a photo
  object is treated as facing the camera); when its legs are not fully
  segmented the floor line comes from the wall rule instead.
Next Step: User evaluation.

## UPDATE-015

Date: 2026-10-01
Phase: Phase 4
Module: Interior Design - provider-agnostic, Download Design

Change:
Final updated requirements: the Interior Design module no longer uses
Gemini (or any cloud AI provider).
  removed         photoreal.py (Gemini image pass), its option in the final
                  dialog, INTERIOR_PHOTOREAL_MODELS, the photoreal test
  segmentation.py documented as a swappable layer: anything implementing
                  segment() + labels (ADE20K) can replace SegFormer
  final image     POST /scenes/{id}/final {format: png|jpg,
                  quality: high(95)|standard(85)} renders with the 2k assets
                  and returns url, filename, size; files/{name}?download=true
                  sends it as an attachment; cached per version and format;
                  original photo untouched
  frontend        "Download Design" button under the canvas and "Download" in
                  the toolbar; dialog with format/quality, automatic download,
                  before/after slider (drag or keyboard); "Reset rotation"
                  buttons in the Rotation/Tilt sections
Status: Completed and tested. Backend 139 pytest; frontend 62 Vitest
  (DownloadDialog.test.jsx new); lint and build OK.
Note: GEMINI_* settings remain for the other modules (2D plans, 3D
  reference photos); the interior module does not read them.

3. Currently Working

This section is the most important section for maintaining development continuity.

It must always describe the current development state.

3.1 Current Status
Live project folder:
D:\New\FYP Website        (four stale copies exist - see ISSUE-001)
Current Phase:
Phase 4 features are being built while Phase 1 authentication is still absent.
The project is not following phase.doc.md order.
Working On:
Interior Design module - photo -> editable room (UPDATE-011), complete and
browser-tested
Current Module:
Interior Design (app/services/interior/, app/api/endpoints/interior.py,
src/components/interior/, src/pages/InteriorDesign.jsx)
Status:
Code complete; pytest (99), Vitest (51) and headless-browser checks pass.
3.2 Current Feature

Current feature being worked on:

Interior Design room editor (UPDATE-011)

Current objective:

User evaluation with their own room photos; then decide the next priority.
3.3 Current Task

Verification only:

1. Stop any running backend/frontend (they were running from a stale copy).
2. Start the backend from D:\New\FYP Website\haven-ai-backend
   (uvicorn app.main:app --reload) and confirm the watch path it prints.
3. Start the frontend from D:\New\FYP Website\haven-ai-react (npm run dev).
4. Confirm http://localhost:8000/openapi.json lists /api/design/3d/generate.
5. Open /3d-design and generate a model, for example:
   "25 x 50 ft plot, 3 bedrooms, 2 bathrooms, kitchen, drawing room,
    TV lounge, car parking, double storey"
3.4 Next Task

In recommended order:

1. Consolidate the duplicate project copies (delete, archive or rename the
   four March copies) so a terminal cannot land in the wrong one again.
2. Put the project under git, add a .gitignore covering .env, __pycache__,
   node_modules, dist and firebase-credentials.json.
3. Move firebase-credentials.json out of the repository and stop hardcoding
   the Firebase web config in src/firebase.js (ISSUE-006).
4. Decide the stack conflict recorded in 1.5: either update the documentation
   to match Firebase + Gemini, or migrate to PostgreSQL + Ollama. Ask the user;
   do not decide this unilaterally.
5. Implement Phase 1: backend authentication, authorization and RBAC. Until
   this exists, the admin and dealer areas are effectively unprotected and
   /api/chat/send trusts any supplied user_id.
6. Replace the remaining mock modules with real implementations: construction
   cost estimation, property recommendation (interior design is done; its
   chatbot intent could link to the editor).
7. Add a test suite (pytest for the backend, Vitest for the frontend).
3.5 Current Development Rule

Do not start large feature implementation until the required architecture and project rules are established.

Development should follow:

Documentation
 ↓
Project Structure
 ↓
Configuration
 ↓
Authentication
 ↓
Core CRUD
 ↓
AI/Advanced Features
 ↓
Testing
 ↓
Deployment
3.6 Active Files

When implementation begins, maintain a list of actively modified files.

Example:

Current Files:

frontend/src/pages/Login.jsx
frontend/src/components/auth/LoginForm.jsx
backend/app/api/auth.py
backend/app/services/auth_service.py
backend/app/models/user.py

This section must be updated whenever the active development area changes.

3.7 Current Development Context

When starting a new session, the AI should first understand:

Current Phase
Current Feature
Current Module
Current Files
Recent Changes
Known Issues
Next Task

Do not assume that unfinished work is complete.

4. Updates
4.1 Update Frequency

Update memory.md whenever a significant event occurs.

Examples:

A feature is completed.
A major architecture decision changes.
A technology decision changes.
A significant bug is fixed.
A new limitation is discovered.
A module is started.
A module is completed.
The current development phase changes.
A major file structure change occurs.
4.2 Do Not Update for Trivial Events

Do not record every:

npm install
pip install
minor CSS adjustment
temporary console error
small typo correction

unless the event has long-term importance.

4.3 Update Format

Use this format for significant updates:

## UPDATE-XXX

Date:
Phase:
Module:
Change:
Reason:
Impact:
Status:
Next Step:

Example:

## UPDATE-001

Date:
Phase: Phase 1
Module: Authentication

Change:
Implemented JWT-based authentication.

Reason:
Required for protected user, dealer, and admin routes.

Impact:
Protected API endpoints can now verify authenticated users.

Status:
Completed

Next Step:
Implement role-based authorization.
4.4 Keep Information Accurate

When updating memory:

Do not claim unfinished work as completed.
Do not record assumptions as facts.
Remove obsolete decisions.
Mark replaced decisions as deprecated.
Keep current status accurate.
Keep file paths accurate.
Keep technology choices synchronized with architecture.md and rules.md.
4.5 Handling Changed Decisions

If a previous decision changes, do not simply overwrite important historical context.

Use:

Previous Decision:
FastAPI + PostgreSQL

New Decision:
FastAPI + PostgreSQL + Redis

Reason:
Caching and session-related requirements.

Then update the current project state.

4.6 Outdated Information

Remove or archive information that is no longer relevant.

For example:

OLD:
Current Module: Authentication


should be changed when the project moves to another module.

Do not allow old information to remain in the "Currently Working" section.

5. Information
5.1 Cross-Session Continuity

This file should allow development to continue even after a new coding session.

A new AI coding session should be able to determine:

What is the project?
What technologies are being used?
What has already been completed?
What is currently being developed?
Which files are being modified?
What decisions have been made?
What problems were solved?
What problems remain?
What should be done next?
5.2 Consistency Across Sessions

The following documents should work together:

PRD.md
    ↓
What to build

architecture.md
    ↓
How the system is structured

rules.md
    ↓
How development must be performed

phase.doc.md
    ↓
What order features should be developed

design.md
    ↓
How the UI/UX should behave

memory.md
    ↓
What has happened and what is happening now
5.3 Source of Truth

Different information has different sources of truth.

Product Requirements
→ PRD.md

Architecture
→ architecture.md

Development Rules
→ rules.md

Development Order
→ phase.doc.md

UI/UX
→ design.md

Current Progress
→ memory.md

If two documents conflict, the conflict must be identified and resolved rather than silently choosing one.

5.4 Important Project Patterns

Record reusable patterns here.

Examples:

Pattern: Service Layer

API routes should call services instead of placing
large amounts of business logic directly inside route handlers.
Pattern: Reusable Components

Common UI components should be reused instead of
creating duplicate components for individual pages.
Pattern: Backend Validation

Important input must be validated on the backend even
when frontend validation already exists.
Pattern: Authorization

Authorization must be enforced at the backend level.
Pattern: AI Routing

AI requests should pass through the centralized AI service
and approved routing logic.
5.5 Important Security Information

Never store secrets in memory.md.

Do not store:

API Keys
Passwords
JWT Secrets
Database Passwords
Private Tokens
Cloud Credentials

Instead, document only where the secret is configured.

Example:

AI API credentials:
Stored in environment variables.
5.6 Important File Locations

Maintain important project paths here.

Example:

Project Root:
/

Frontend:
frontend/

Backend:
backend/

Documentation:
docs/

Database:
backend/app/models/

API:
backend/app/api/

Services:
backend/app/services/

AI:
backend/app/services/ai/

Authentication:
backend/app/services/auth/

Frontend Components:
frontend/src/components/

Frontend Pages:
frontend/src/pages/

Update these paths if the project structure changes.

6. Memory Maintenance
6.1 Before Starting a Development Session

The AI should:

1. Read memory.md.
2. Read relevant project documentation.
3. Identify the current phase.
4. Identify the current task.
5. Inspect the current implementation.
6. Continue from the existing state.

Do not restart completed work without a reason.

6.2 After Completing a Major Task

The AI should:

1. Update completed tasks.
2. Update current module.
3. Update current file(s).
4. Record important decisions.
5. Record important issues and solutions.
6. Define the next task.
6.3 Before Ending a Development Session

Verify:

[ ] Current status is accurate
[ ] Completed tasks are updated
[ ] Current feature is correct
[ ] Current file/module is correct
[ ] Known issues are recorded
[ ] Next task is defined
[ ] Outdated information is removed
6.4 Memory Quality Rules

Memory must be:

Accurate
Concise
Current
Useful
Project-specific
Actionable

Avoid:

Conversation transcripts
Repeated information
Temporary debugging output
Personal opinions
Unverified assumptions
Sensitive credentials
7. Session Handoff

If development is interrupted, the Currently Working section must contain enough information for the next session to continue.

Use:

Working On:
[Feature]

Current Module:
[Module]

Current File:
[File]

Completed:
[What is finished]

In Progress:
[What is partially finished]

Issue:
[Known problem]

Next:
[Exact next task]

Example:

Working On:
User Authentication

Current Module:
Authentication

Current File:
backend/app/api/auth.py

Completed:
User registration and password hashing.

In Progress:
Login endpoint.

Issue:
JWT token validation still needs to be added.

Next:
Implement authentication middleware and protected routes.
8. Project Progress Summary
Documentation
[x] PRD
[x] Architecture
[x] Rules
[x] Development Phases
[x] Design
[x] Memory
Phase 1 — Authentication
[ ] Registration
[ ] Login
[ ] Logout
[ ] Password Reset
[ ] Authentication
[ ] Authorization
[ ] RBAC
[ ] Protected Routes
Phase 2 — Dashboard
[ ] User Dashboard
[ ] Dealer Dashboard
[ ] Admin Dashboard
[ ] Navigation
[ ] Statistics
[ ] Charts
Phase 3 — CRUD
[ ] User CRUD
[ ] Dealer CRUD
[ ] Property CRUD
[ ] Property Images
[ ] Search
[ ] Filtering
[ ] Sorting
[ ] Pagination
[ ] Chat Operations
Phase 4 — AI and Advanced Features
[x] Centralized AI Chatbot        Gemini-backed, working (UPDATE-001)
[x] Intent Detection              keyword/regex router, not ML
[x] AI Routing                    routes to 5 module keys
[ ] Property Recommendation       MOCK data only
[ ] 2D Design                     built then removed on request (UPDATE-002)
[x] 3D Design                     built and tested (UPDATE-004)
[ ] Interior Design               MOCK data only
[ ] Construction Cost Estimation  MOCK data only
[ ] User-Dealer Chat              UI only, no backend API
[ ] File Upload
[ ] File Download
[ ] Notifications
[ ] Settings
Phase 5 — Testing
[ ] Unit Testing
[ ] Integration Testing
[ ] AI Testing
[ ] Security Testing
[ ] Performance Testing
[ ] Bug Fixing
[ ] Regression Testing
Phase 6 — Deployment
[ ] Docker Setup
[ ] Staging
[ ] Production
[ ] Monitoring
[ ] Feedback
[ ] Maintenance
9. Final Memory Principle

The purpose of memory.md is:

Preserve the important state of the project so that development can continue consistently across sessions without losing decisions, progress, problems, or the next required action.

The AI must treat memory.md as a project-state document, not as a complete history of every action taken during development.

The most important information to keep current is:

CURRENT PHASE
      ↓
CURRENT FEATURE
      ↓
CURRENT MODULE
      ↓
CURRENT FILE
      ↓
COMPLETED WORK
      ↓
KNOWN ISSUES
      ↓
NEXT TASK

When these seven pieces of information are accurate, another development session can continue the project with minimal context loss.


### How `memory.md` fits with your other files

Your documentation system now has a very clear separation:

```text
                    AI CODING AGENT
                          │
          ┌───────────────┼────────────────┐
          │               │                │
          ▼               ▼                ▼
       PRD.md       architecture.md     rules.md
          │               │                │
       WHAT            HOW SYSTEM       WHAT RULES
          │               │                │
          └───────────────┼────────────────┘
                          │
                          ▼
                    phase.doc.md
                          │
                    WHEN TO BUILD
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
        design.md                 memory.md
          HOW UI LOOKS             CURRENT STATE
                                      │
                                      ▼
                                  NEXT TASK

One important point: memory.md should be updated by Claude Code after meaningful development work, not after every single command. Otherwise it will become huge and eventually become less useful than the actual source code and documentation.