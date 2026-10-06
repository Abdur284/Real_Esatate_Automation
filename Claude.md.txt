# CLAUDE.md
AI-Powered Real Estate Platform
Project Instructions for Claude Code
1. PROJECT IDENTITY
Project Name
AI-Powered Real Estate Platform
Project Type
Final Year Project
Project Purpose
This is an existing full-stack AI-powered real estate platform.
The platform is intended to provide users with:- Property search and exploration.- Property recommendations.- Construction cost estimation.- 2D design functionality.- 3D design functionality.- Interior design functionality.- A centralized AI chatbot.- AI-based request/intent routing.- Communication between users and dealers.- User accounts and authentication.- Dealer functionality.- Admin functionality.- Notifications and alerts.- File upload/download.- User settings and preferences.
The project is already under development. It is NOT a blank project.
2. CRITICAL RULE — INSPECT BEFORE
MODIFYING
This is an EXISTING project.
Claude Code MUST NOT assume that the project is empty.
Before creating, replacing, refactoring, or deleting code, inspect the existing
implementation.
The following already exist or have already been developed:- Frontend- Backend- Property Recommendation Module- Construction Cost Estimation Module
These existing modules are considered protected working components unless:
1. The user explicitly asks for changes.
2. A bug requires a modification.
3. A documented architectural problem requires a modification.
4. A required integration genuinely needs a change.
DO NOT:- Recreate the frontend from scratch.- Recreate the backend from scratch.- Recreate the recommendation module.- Recreate the cost estimation module.- Replace working code unnecessarily.- Create duplicate modules.- Change architecture without understanding the current architecture.
First understand what exists. Then make the smallest appropriate change.
3. FIRST ACTION — PROJECT INSPECTION
When Claude Code starts working on this project for the first time, the first
task is PROJECT INSPECTION.
Do not immediately start coding.
Inspect:
1. Complete project folder structure.
2. Frontend structure.
3. Backend structure.
4. Existing database configuration.
5. Existing database models.
6. Existing API endpoints.
7. Existing React pages.
8. Existing React components.
9. Existing services and API clients.
10. Existing authentication implementation.
11. Property Recommendation Module.
12. Construction Cost Estimation Module.
13. Existing AI/LLM integration.
14. Existing routing logic.
15. Environment configuration.
16. Docker configuration.
17. Dependency/package files.
18. Existing tests.
19. Existing documentation.
20. Existing configuration files.
Determine:- What is already implemented?- What is working?- What is partially implemented?- What is broken?- What is missing?- Which modules communicate with each other?- Which APIs already exist?- Which components can be reused?- Which services already exist?- Which database tables already exist?- Which technologies are actually being used?- Which parts should not be changed?
Do not make assumptions when the codebase can answer the question.
4. INSPECTION REPORT
After the initial inspection, provide a concise project understanding report.
The report should include:
Architecture- Frontend technology.- Backend technology.- Database technology.- AI technology.- Communication flow.
Existing Modules- Module name.- Location.- Purpose.- Current status.
Existing APIs- Important endpoints.- What they do.- Which frontend features use them.
Database- Existing tables/models.- Relationships.- Important constraints.
Problems Found- Bugs.- Configuration problems.- Security concerns.- Code duplication.- Missing validation.- Performance concerns.
Recommendations
Only recommend changes that are relevant and justified.
Do not automatically implement every recommendation.
5. APPROVED TECHNOLOGY STACK
Use the existing project technology stack where it is already established.
The approved target stack is:
Frontend- React- JavaScript- Tailwind CSS
Backend- Python- FastAPI
Database- PostgreSQL- SQLAlchemy- Alembic
AI- Ollama
Containers- Docker- Docker Compose
Version Control- Git
If the existing implementation uses a different technology, DO NOT replace it
automatically.
First inspect why it is being used and determine whether migration is actually
necessary.
Ask the user before making a major technology migration.
6. DOCUMENTATION — READ BEFORE MAJOR
WORK
Read the relevant documentation before making significant changes.
Read in this order when performing broad project work:
1. docs/PRD.md
2. docs/architecture.md
3. docs/rules.md
4. docs/phase.doc.md
5. docs/design.md
6. docs/database.md
7. docs/memory.md
Documentation Purpose
PRD.md- Defines product requirements and goals.
architecture.md- Defines system architecture and module interaction.
rules.md- Defines technologies, coding conventions, security, AI boundaries,
dependencies, error handling, testing, and general rules.
phase.doc.md
- Defines the planned development phases.
design.md- Defines UI/UX, colors, typography, responsiveness, accessibility,
themes, and UI preferences.
database.md- Defines database structure, entities, relationships, constraints,
indexes, and migrations.
memory.md- Defines current project status, completed work, decisions, issues,
and the next tasks.
7. SOURCE OF TRUTH
Use each document for its intended purpose.
| Document | Purpose |
|---|---|
| PRD.md | Product requirements |
| architecture.md | System architecture |
| rules.md | Development rules |
| phase.doc.md | Development phases |
| design.md | UI/UX |
| database.md | Database design |
| memory.md | Current project state |
| Source code | Actual implementation |
If documentation conflicts with the actual code:
1. Inspect the code.
2. Identify the difference.
3. Do not silently rewrite working code.
4. Determine whether documentation is outdated.
5. Update documentation when appropriate.
If a conflict affects architecture, security, database design, or major
requirements, ask the user before making a major change.
8. DEVELOPMENT MODE
The project is currently in EXISTING/ITERATIVE DEVELOPMENT mode.
Claude Code must NOT assume that development starts from Phase 1.
The current task is determined by the user's request.
Examples:- If the user reports a bug, debug the existing implementation.- If the user requests a UI change, inspect the existing UI first.- If the user requests a new feature, inspect the architecture before adding it.- If the user requests an AI module, inspect existing AI integrations first.- If the user requests database changes, inspect the current schema first.
Follow the relevant phase from docs/phase.doc.md when implementing new
features.
9. BUG-FIXING WORKFLOW
When the user reports a bug:
1. Understand the reported behavior.
2. Reproduce the issue when possible.
3. Locate the relevant code.
4. Trace the execution flow.
5. Identify the root cause.
6. Determine whether the issue is:- Frontend- Backend- Database- AI- API integration- Authentication- Configuration- Deployment- Dependency related
7. Explain the root cause briefly.
8. Make the smallest appropriate fix.
9. Do not rewrite unrelated code.
10. Run relevant tests.
11. Verify the affected feature.
12. Check for regressions.
13. Update documentation/memory if the fix is significant.
Do not hide symptoms when the root cause can be fixed properly.
10. FEATURE-CHANGE WORKFLOW
When the user requests a new feature or change:
1. Understand the requirement.
2. Inspect the existing implementation.
3. Search for similar existing functionality.
4. Identify reusable components/services.
5. Identify affected modules.
6. Identify database/API changes if required.
7. Check architectural compatibility.
8. Create a short implementation plan.
9. Implement the change.
10. Test the change.
11. Test related existing functionality.
12. Update documentation if necessary.
13. Update memory.md when the change is significant.
Do not create a parallel implementation when an existing implementation can
be extended safely.
11.1 Frontend
11. EXISTING MODULES
The frontend has already been created.
Claude Code must inspect the existing frontend before modifying it.
Do not rebuild the frontend from scratch.
Reuse:- Existing pages.- Existing layouts.- Existing components.- Existing routing.- Existing API services.- Existing styling patterns.- Existing state management.
Only introduce new patterns when necessary.
11.2 Backend
The backend has already been created.
Inspect:- FastAPI application structure.- API routes.
- Services.- Schemas.- Models.- Repositories.- Authentication.- Configuration.- Middleware.- Error handling.
Do not recreate the backend.
11.3 Property Recommendation Module
The Property Recommendation Module already exists.
Before modifying it:- Inspect its source code.- Understand its input data.- Understand its output.- Understand its API.- Understand how the frontend communicates with it.- Identify its model/algorithm.- Identify its dependencies.- Check current bugs and limitations.
Do not replace the recommendation system without explicit justification.
11.4 Construction Cost Estimation Module
The Construction Cost Estimation Module already exists.
Before modifying it:- Inspect its calculation logic.- Inspect input validation.- Inspect cost parameters/data.- Inspect API integration.- Inspect frontend integration.- Check edge cases.- Check error handling.
Do not rewrite working calculations without a documented reason.
12. FUTURE / PLANNED AI FEATURES
The platform is intended to support AI features including:
- Centralized AI chatbot.- Intent detection.- Request routing.- Property-related questions.- Property recommendation assistance.- Construction cost estimation assistance.- 2D design assistance.- 3D design assistance.- Interior design assistance.
The centralized chatbot should eventually act as the main conversational
entry point and route requests to the appropriate module/service.
The AI layer must integrate with the existing architecture instead of bypassing
it.
13. AI SECURITY AND BOUNDARIES
Ollama is the approved AI runtime.
AI requests should follow:
React
fl
FastAPI
fl
AI Service
fl
Ollama
fl
AI Model
AI MUST NOT:- Bypass authentication.- Bypass authorization.- Grant admin privileges.- Directly modify the database.- Execute arbitrary operating-system commands.- Expose private user data.- Invent real property records.- Claim fabricated information is verified.- Modify protected resources without backend authorization.
AI output must be treated as untrusted data.
The backend remains the final authority for permissions, business rules, and
database operations.
14. USER ROLES
The platform may contain:- Visitor- User- Dealer- Admin
A visitor is an unauthenticated user state and does not necessarily need a
database account.
User
May access normal authenticated user functionality.
Dealer
May manage dealer-specific functionality and communicate with users according
to the defined permissions.
Admin
Has administrative control over the platform.
Admin permissions MUST be enforced by the backend.
The frontend must never be the only authorization mechanism.
15. ARCHITECTURE RULES
Target communication flow:
React
fl
FastAPI
fl
Services / Business Logic
fl
Repositories / ORM
fl
PostgreSQL
AI:
React
fl
FastAPI
fl
AI Service
fl
Ollama
Rules:- React must not connect directly to PostgreSQL.- React must not connect directly to Ollama.- Business logic belongs in backend services.- API routes should remain thin.- Database operations belong behind the backend.- Reuse existing services.- Reuse existing React components.- Avoid circular dependencies.- Avoid unnecessary architectural complexity.- Preserve existing architecture unless a justified change is required.
16. DATABASE RULES
PostgreSQL is the approved primary database.
Use:- SQLAlchemy.- Alembic.
Rules:- Inspect the existing database before changing it.- Do not recreate existing tables.- Use migrations for schema changes.- Preserve existing data when possible.- Use foreign keys for relationships.- Use appropriate constraints.- Add indexes where justified.- Use transactions for multi-step operations.- Validate ownership of resources.- Never expose database credentials.- Never connect to PostgreSQL from React.- Never store secrets in source code.
Database-specific details are defined in:
docs/database.md
17. SECURITY RULES
Never:- Hardcode passwords.- Hardcode API keys.- Hardcode database credentials.- Commit secrets.- Store plaintext passwords.- Trust frontend authorization.- Expose private user information.- Allow unauthorized resource access.- Allow normal users to access admin functionality.
Always:- Hash passwords securely.- Validate backend input.- Authenticate protected requests.- Authorize protected operations.- Validate resource ownership.- Use environment variables for secrets.- Validate uploaded files.- Use safe database access.- Return safe user-facing errors.
18. FRONTEND RULES
Use React and the existing frontend architecture.
Use Tailwind CSS according to the existing design system.
Frontend must be:- Responsive.- Mobile-friendly.- Accessible.- Consistent.- Reusable.- Easy to navigate.
Reuse existing:- Components.- Layouts.- Forms.- Buttons.- Cards.- Navigation.
- Modals.- API services.
Do not create duplicate UI components when an equivalent component already
exists.
Follow docs/design.md.
19. BACKEND RULES
Use FastAPI and the existing backend architecture.
Preferred flow:
API Route
fl
Schema / Validation
fl
Service
fl
Repository / ORM
fl
Database
Rules:- Keep route handlers small.- Put business logic in services.- Use Pydantic schemas for validation.- Use SQLAlchemy for database operations.- Handle exceptions consistently.- Protect private endpoints.- Validate resource ownership.- Avoid duplicate business logic.
20. API RULES
Follow the existing API conventions before creating new endpoints.
Authentication examples:
POST /api/auth/signup
POST /api/auth/login
POST /api/auth/logout
POST /api/auth/refresh
POST /api/auth/forgot-password
POST /api/auth/reset-password
Do not create duplicate endpoints.
Before creating an endpoint:
1. Search existing routes.
2. Check whether the operation already exists.
3. Reuse or extend the existing endpoint when appropriate.
4. Maintain consistent request/response structures.
21. ERROR HANDLING
Backend:- Use correct HTTP status codes.- Validate input.- Return structured errors.- Log useful technical details.- Do not expose stack traces in production.- Do not log secrets.
Frontend:- Show friendly error messages.- Show loading states.- Show empty states.- Handle network errors.- Handle authentication errors.- Provide fallbacks where appropriate.
Technical debugging information belongs in logs, not normal user-facing
messages.
22. DEPENDENCY RULES
Do not install packages without checking the existing project first.
Before adding a dependency:
1. Check existing dependencies.
2. Check docs/rules.md.
3. Check whether the functionality already exists.
4. Determine whether the dependency is necessary.
5. Prefer stable and maintained packages.
6. Avoid unnecessary dependencies.
Do not replace approved technologies without explicit approval.
Do not introduce:- MongoDB instead of PostgreSQL.- Express instead of FastAPI.- Next.js instead of React.- A different primary AI runtime instead of Ollama.
Do not migrate existing technology simply for personal preference.
23. TESTING RULES
When changing code:
1. Run relevant tests before the change when possible.
2. Implement the change.
3. Add/update tests.
4. Run the relevant tests.
5. Run regression tests when appropriate.
6. Fix failures.
7. Verify the final behavior.
Test:- Authentication.- Authorization.- API endpoints.- Services.- Database operations.- Validation.- Existing recommendation module.- Existing cost estimation module.- AI routing when implemented.- Important frontend behavior.
Do not mark a feature complete without appropriate verification.
24. PERFORMANCE RULES
Prefer simple and efficient implementations.
Avoid:- Unnecessary database queries.- N+1 queries.- Repeated API calls.- Large unnecessary frontend renders.- Loading large datasets without pagination.- Expensive AI calls when unnecessary.
Use:- Pagination.- Appropriate database indexes.- Caching where justified.- Lazy loading where useful.- Efficient queries.- Appropriate API response sizes.
Do not optimize prematurely without evidence.
25. FILE UPLOAD RULES
If file upload functionality is implemented:- Validate file type.- Validate file size.- Sanitize file names.- Do not trust client-provided MIME types alone.- Store files safely.- Prevent unauthorized access.- Do not execute uploaded files.- Validate permissions before download.
Use Git.
Preferred commit prefixes:
feat:
fix:
test:
refactor:
docs:
chore:
Examples:
feat: add dealer chat endpoint
fix: resolve recommendation API error
test: add authentication tests
refactor: simplify property service
docs: update architecture
26. GIT RULES
chore: update dependency
Never commit:- .env files containing secrets.- Passwords.- API keys.- Database credentials.- Temporary files.- Build artifacts.- Unnecessary generated files.
27. BEFORE CODING CHECKLIST
Before making a change:
[ ] Understand the user's request.
[ ] Inspect relevant existing code.
[ ] Read relevant documentation.
[ ] Check memory.md.
[ ] Search for existing functionality.
[ ] Identify affected modules.
[ ] Identify dependencies.
[ ] Check security implications.
[ ] Check database implications.
[ ] Check API implications.
[ ] Make a short implementation plan.
Do not code blindly.
28. AFTER CODING CHECKLIST
After making a change:
[ ] Run tests.
[ ] Check for runtime errors.
[ ] Check API behavior.
[ ] Check frontend behavior.
[ ] Check database behavior if affected.
[ ] Check security.
[ ] Check regression risks.
[ ] Review changed files.
[ ] Update documentation if necessary.
[ ] Update memory.md for significant changes.
[ ] Report what was changed.
[ ] Report remaining issues.
29. DOCUMENTATION UPDATE RULE
Update documentation when a change affects:- Architecture.- Database schema.- API contracts.- Technology stack.- Security rules.- UI/UX.- Development phases.- Major feature decisions.
Update:
docs/memory.md
when significant work is completed.
Do not unnecessarily rewrite documentation.
30. MEMORY MANAGEMENT
memory.md should record:- Major completed features.- Current work.- Important architectural decisions.- Database decisions.- Major bugs and solutions.- Current problems.- Important dependencies.- Next tasks.
Update memory regularly.
Remove outdated information.
Never claim a feature is complete when it is not.
31. MAJOR CHANGE POLICY
Ask the user before making major changes to:- Technology stack.- Database technology.- Core architecture.- Authentication strategy.- AI architecture.- User roles.- Core database model.
- API contracts.- Major folder structure.- Existing working modules.
Small implementation decisions can be made independently when they follow the
documentation and do not alter the architecture.
32. WHAT NOT TO DO
DO NOT:- Start coding before inspecting an existing module.- Recreate the project.- Rewrite working modules unnecessarily.- Create duplicate components.- Create duplicate APIs.- Replace existing technologies without justification.- Ignore documentation.- Ignore existing code.- Skip tests.- Put secrets in source code.- Put database access in React.- Put Ollama access directly in React.- Allow AI to bypass authorization.- Build unrelated features.- Modify unrelated files unnecessarily.- Delete existing functionality without approval.
DO:- Inspect first.- Understand before modifying.- Reuse existing code.- Preserve working functionality.- Fix root causes.- Make minimal targeted changes.- Follow the architecture.- Follow the documentation.- Test changes.- Check for regressions.- Keep security in mind.- Update memory.- Explain significant decisions.
33. WHAT TO DO- Ask before major architectural changes.
34. CURRENT PROJECT STATUS
The following major work has already been completed:
[x] Frontend
[x] Backend
[x] Property Recommendation Module
[x] Construction Cost Estimation Module
[x] PRD documentation
[x] Architecture documentation
[x] Rules documentation
[x] Phase documentation
[x] Design documentation
[x] Memory documentation
[x] Database documentation
Planned or remaining work may include:
[ ] Authentication improvements/completion
[ ] Dashboard improvements
[ ] Property CRUD improvements
[ ] Centralized AI Chatbot
[ ] Intent Detection
[ ] AI Request Routing
[ ] 2D Design
[ ] 3D Design
[ ] Interior Design
[ ] User-Dealer Chat
[ ] Notifications
[ ] File Management
[ ] Settings/Preferences
[ ] Comprehensive Testing
[ ] Deployment
[ ] Maintenance
This checklist is a high-level summary.
For the detailed current state, always check docs/memory.md.
35. CURRENT TASK
There is no permanent hard-coded current task in this file.
The current task is determined by the user's latest request.
Before beginning the task:
1. Inspect the relevant existing implementation.
2. Check docs/memory.md.
3. Check the relevant project documentation.
4. Determine the safest integration point.
5. Plan the change.
6. Implement.
7. Test.
8. Document significant changes.
36. WHEN THE USER REQUESTS A CHANGE
Use this process:
USER REQUEST
fl
UNDERSTAND
fl
INSPECT EXISTING CODE
fl
CHECK DOCUMENTATION
fl
IDENTIFY IMPACT
fl
PLAN
fl
IMPLEMENT
fl
TEST
fl
VERIFY
fl
DOCUMENT
fl
REPORT
Do not skip inspection.
37. WHEN THE USER REPORTS A BUG
Use this process:
BUG REPORT
fl
REPRODUCE
fl
TRACE
fl
FIND ROOT CAUSE
fl
PLAN FIX
fl
MINIMAL CHANGE
fl
TEST
fl
REGRESSION CHECK
fl
DOCUMENT
fl
REPORT
Do not rewrite an entire module to fix a localized bug unless there is a
technical reason.
38. WHEN THE USER REQUESTS A NEW MODULE
Before creating a new module:
1. Inspect the architecture.
2. Check whether similar functionality already exists.
3. Determine where the module belongs.
4. Determine its API requirements.
5. Determine database requirements.
6. Determine frontend requirements.
7. Determine AI requirements if applicable.
8. Check security requirements.
9. Check phase requirements.
10. Create an implementation plan.
The new module must integrate with the existing system.
39. FINAL PRINCIPLE
The project must be developed incrementally and safely.
The most important principle is:
"UNDERSTAND THE EXISTING PROJECT BEFORE CHANGING IT."
Prefer:- Correctness over speed.- Reuse over duplication.- Root-cause fixes over temporary patches.
- Security over convenience.- Maintainability over unnecessary complexity.- Testing over assumptions.- Documentation over forgotten decisions.
Claude Code is an implementation assistant for the existing project.
It must preserve the user's existing work and make changes deliberately.
END OF CLAUDE.md