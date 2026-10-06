# AI-Powered Real Estate Platform
## Development Rules and Engineering Standards

**Document:** `rules.md`
**Version:** 1.0
**Status:** Active
**Purpose:** Define the technologies, development practices, coding standards, security requirements, AI boundaries, testing rules, and engineering conventions that must be followed throughout the project.

---

# 1. What to Use

This section defines the approved technologies, frameworks, architectural patterns, tools, and conventions for the project.

---

## 1.1 Frontend

### Approved Technologies

- React
- JavaScript
- Tailwind CSS
- React Router
- Vite

### Frontend Architecture

Use a component-based architecture.

Preferred structure:

```text
components/
pages/
layouts/
services/
hooks/
context/
utils/
constants/
routes/
Rules
Use React functional components.
Use React Hooks where appropriate.
Create reusable components instead of duplicating UI code.
Keep components focused on presentation and interaction.
Keep API communication inside service/API modules.
Do not place sensitive business logic in frontend code.
Use Tailwind CSS for styling.
Use responsive design by default.
Use React Router for navigation.
Use Vite as the frontend build tool.
1.2 Backend
Approved Technologies
Python
FastAPI
Pydantic
SQLAlchemy
PostgreSQL
Backend Architecture

Use a modular layered architecture:

API Routes
    ↓
Services
    ↓
Repositories
    ↓
Database

Example:

Request
   ↓
Router
   ↓
Schema Validation
   ↓
Authentication / Authorization
   ↓
Service
   ↓
Repository
   ↓
Database
Rules
Use FastAPI for API development.
Use Pydantic for request and response validation.
Use SQLAlchemy for database interaction.
Keep business logic out of route handlers whenever practical.
Keep database queries inside repository/data-access layers.
Use dependency injection where appropriate.
Use asynchronous operations where they provide a meaningful benefit.
Return consistent API responses.
Use HTTP status codes correctly.
1.3 Database
Approved Database

PostgreSQL.

Database Rules
Use relational database design.
Define primary keys for entities.
Define foreign keys for relationships.
Use appropriate indexes.
Use constraints to maintain data integrity.
Avoid unnecessary duplication of data.
Use migrations for schema changes.
Never manually modify production database schemas without documenting the change.
1.4 AI
Approved AI Runtime

Ollama.

Architecture:

Frontend
   ↓
FastAPI
   ↓
AI Service
   ↓
Ollama
   ↓
AI Model
AI Rules
Frontend must never communicate directly with Ollama.
AI requests must go through the backend.
AI functionality must be isolated inside an AI service/module.
AI models must be configurable.
Model names must not be hardcoded throughout the application.
AI prompts should be centralized and version-controlled where practical.
AI output must be validated before being used for critical application actions.
AI must not be treated as an authoritative source for safety-critical or legally binding decisions.
1.5 API

Use REST APIs for frontend-backend communication.

Preferred format:

/api/auth/*
/api/users/*
/api/dealers/*
/api/properties/*
/api/chat/*
/api/ai/*
/api/recommendations/*
/api/design/*
/api/cost-estimation/*
/api/admin/*

Use JSON for normal request and response payloads.

1.6 Authentication

Use secure authentication mechanisms.

Requirements:

Password hashing.
Secure authentication tokens/session mechanism.
Protected endpoints.
Role-based authorization.
Backend authorization checks.

Roles:

Visitor
User
Dealer
Admin
1.7 Authorization

Use Role-Based Access Control (RBAC).

Example:

USER
→ User functionality

DEALER
→ Dealer functionality

ADMIN
→ Administrative functionality

Authorization must always be enforced by the backend.

Frontend route protection is only an additional user-experience layer.

1.8 Containerization

Use:

Docker
Docker Compose

Expected services may include:

frontend
backend
postgres
ollama

Docker configuration must be reproducible.

1.9 Version Control

Use Git.

Recommended branch structure:

main
develop
feature/*
bugfix/*
hotfix/*

Do not commit directly to main during normal feature development.

1.10 Architecture Pattern

Use a modular monolithic architecture.

Do not introduce microservices unless there is a clear requirement.

Preferred:

One Application
│
├── Authentication
├── Users
├── Dealers
├── Properties
├── Chat
├── AI
├── Recommendations
├── Design
├── Cost Estimation
└── Admin
2. What to Avoid

This section defines technologies, patterns, packages, and practices that should not be used without explicit approval.

2.1 Avoid Unnecessary Technologies

Do not introduce additional frameworks or platforms simply because they are popular.

Examples:

Do not add:
- Next.js
- Django
- Flask
- Express.js
- MongoDB
- Redis
- Kubernetes

unless there is a documented architectural reason to use them.

The project already has an approved stack.

2.2 Avoid Multiple Backend Frameworks

Do not mix:

FastAPI + Django
FastAPI + Flask
FastAPI + Express

FastAPI is the approved backend framework.

2.3 Avoid Multiple Databases Without a Requirement

Do not introduce MongoDB, Firebase, SQLite, Redis, or another database unless a specific requirement justifies it.

PostgreSQL is the primary database.

SQLite may only be used temporarily for isolated testing if required.

2.4 Avoid Direct Database Access from Frontend

Never allow:

React
  ↓
PostgreSQL

The correct architecture is:

React
  ↓
FastAPI
  ↓
PostgreSQL
2.5 Avoid Direct AI Access from Frontend

Never use:

React
  ↓
Ollama

Use:

React
  ↓
FastAPI
  ↓
AI Service
  ↓
Ollama

This protects the system architecture and prevents exposing internal services.

2.6 Avoid Hardcoded Secrets

Never write:

PASSWORD = "mypassword"
JWT_SECRET = "secret123"
API_KEY = "abcdef"

Use environment variables.

.env
.env.example

Real .env files must not be committed to Git.

2.7 Avoid Plain-Text Passwords

Never store passwords directly.

Passwords must be securely hashed before storage.

2.8 Avoid Business Logic in UI Components

Do not create large React components containing:

UI
+
API calls
+
Database logic
+
Business rules
+
Authentication logic
+
AI logic

Instead:

Component
   ↓
Service
   ↓
Backend API
   ↓
Business Service
2.9 Avoid Duplicate Code

Do not copy and paste the same logic into multiple files.

Create reusable:

Components
Functions
Services
Hooks
Utilities

where appropriate.

2.10 Avoid Overengineering

Do not implement complex infrastructure when a simple solution is sufficient.

For example:

Do not introduce microservices when a modular monolith solves the requirement.

Do not introduce Kubernetes for a university FYP unless specifically required.

Do not add message queues unless asynchronous processing actually requires them.

2.11 Avoid Blind AI-Generated Code

AI-generated code must be reviewed.

Claude Code or another AI coding agent must:

Inspect existing code.
Understand the architecture.
Implement the requested change.
Check for conflicts.
Run appropriate tests.
Report problems.

AI output must not automatically be considered correct.

2.12 Avoid Unnecessary Comments

Do not write comments that merely describe obvious code.

Bad:

# Increment i by 1
i += 1

Good:

# Retry because the external AI service may temporarily refuse requests.

Comments should explain reasoning or non-obvious behavior.

2.13 Avoid Ignoring Errors

Never silently ignore exceptions.

Bad:

try:
    process()
except:
    pass

Exceptions must either:

Be handled.
Be logged.
Be converted into an appropriate application error.
Be deliberately re-raised.
3. Libraries and Dependencies

Dependencies must be kept minimal and purposeful.

Exact versions should be pinned or constrained in dependency files once the project environment is stabilized.

3.1 Frontend Dependencies
Library	Purpose	Version Guideline
React	UI framework	Use current stable version compatible with project
React DOM	React browser rendering	Match React version
React Router	Routing	Current stable compatible version
Tailwind CSS	Styling	Current stable compatible version
Vite	Build tool	Current stable compatible version
Axios or Fetch	HTTP communication	Prefer native Fetch unless Axios provides clear value
Rule

Do not install a dependency when the same functionality can reasonably be implemented using the existing stack.

3.2 Backend Dependencies
Library	Purpose	Version Guideline
FastAPI	Backend API framework	Stable version
Uvicorn	ASGI server	Stable compatible version
Pydantic	Data validation	Compatible with FastAPI
SQLAlchemy	ORM/database access	Stable version
PostgreSQL driver	PostgreSQL connection	Stable compatible version
Alembic	Database migrations	Compatible with SQLAlchemy
Password hashing library	Secure password storage	Stable maintained version
JWT/auth library	Authentication	Stable maintained version
HTTP client	External service communication	Stable maintained version

The exact package versions should be recorded in:

backend/requirements.txt
3.3 AI Dependencies

The AI layer should use:

Ollama

Communication should occur through the backend AI service.

Avoid adding multiple AI frameworks unless required.

3.4 Testing Dependencies

Use appropriate testing tools for the chosen stack.

Backend:

pytest

Frontend:

Vitest
React Testing Library

Use end-to-end testing tools only when required by project scope.

3.5 Dependency Management Rules

Before adding a dependency:

Determine whether the functionality already exists.
Check whether an existing approved library can solve it.
Check whether the dependency is maintained.
Check compatibility with the current stack.
Consider security implications.
Document the reason for adding it.

Do not add dependencies simply because an AI coding agent recommends them.

4. Error Handling

Error handling must be consistent across the entire application.

4.1 Frontend Errors

The frontend should display user-friendly messages.

Bad:

AxiosError: Request failed with status code 500

Good:

Something went wrong while loading the properties.
Please try again.

Technical details should not normally be shown to users.

4.2 Backend Errors

The backend should return appropriate HTTP status codes.

Examples:

400 → Bad Request
401 → Authentication Required
403 → Permission Denied
404 → Resource Not Found
409 → Conflict
422 → Validation Error
429 → Too Many Requests
500 → Internal Server Error
503 → External Service Unavailable
4.3 Error Response Format

Use a consistent structure.

Example:

{
  "success": false,
  "error": {
    "code": "PROPERTY_NOT_FOUND",
    "message": "The requested property could not be found."
  }
}

Do not expose:

Stack traces
Database errors
Password information
Internal file paths
Environment variables
AI system prompts
Internal implementation details
4.4 Logging

Backend errors should be logged appropriately.

Logs should include useful information such as:

Timestamp
Log level
Module
Endpoint
Error type
Request correlation ID where available

Do not log sensitive information.

Never log:

Passwords
Authentication tokens
API keys
Private messages unnecessarily
Personal sensitive information
4.5 Error Levels

Use appropriate log levels:

DEBUG
INFO
WARNING
ERROR
CRITICAL

Example:

INFO
User successfully authenticated.

WARNING
AI service response exceeded expected latency.

ERROR
Database request failed.

CRITICAL
Application cannot connect to required database.
4.6 User-Friendly Fallbacks

If a non-critical service fails, the application should degrade gracefully.

Example:

Ollama unavailable
      ↓
AI feature unavailable
      ↓
Display:
"AI assistance is temporarily unavailable.
Please try again later."

The entire website should not necessarily become unavailable because the AI service is temporarily offline.

4.7 Validation Errors

Validate input at multiple levels:

Frontend
   ↓
Backend/Pydantic
   ↓
Business Logic
   ↓
Database Constraints

Frontend validation improves user experience.

Backend validation provides actual security and correctness.

5. Boundaries of AI

AI is an assisting component of the platform, not the authority over the entire system.

5.1 What AI Can Do

The AI system may:

Answer supported real-estate questions.
Provide conversational assistance.
Identify user intent.
Route supported requests.
Assist with property discovery.
Explain property information.
Assist with construction-related calculations where deterministic tools are used.
Assist users in understanding design concepts.
Provide recommendations when appropriate.
Help users navigate platform functionality.
Generate natural-language responses.
5.2 What AI Cannot Do

AI must not independently:

Modify the database without authorization.
Delete user data without explicit application-level authorization.
Create an administrator account.
Change user roles.
Bypass authentication.
Bypass authorization.
Access another user's private information.
Expose passwords or tokens.
Reveal system secrets.
Execute arbitrary server commands.
Modify application source code during normal user interaction.
Make legally binding property decisions.
Guarantee property prices.
Guarantee construction costs.
Guarantee investment returns.
Present uncertain information as verified fact.
5.3 AI Must Not Replace Deterministic Logic

Where a calculation can be performed deterministically, use normal application logic.

Example:

Construction Cost
        ↓
Calculation Engine
        ↓
Result

rather than:

Construction Cost
        ↓
LLM Guess
        ↓
Result

The AI can explain the result, but deterministic calculations should be performed by software logic.

5.4 AI Hallucination Control

AI-generated information must be treated as potentially uncertain.

The system should:

Use application data where available.
Avoid inventing property information.
Clearly communicate uncertainty.
Avoid fabricating prices, locations, dealers, or listings.
Prefer verified database information for factual property details.
5.5 AI Routing Boundaries

The AI routing system may identify intent such as:

PROPERTY_SEARCH
PROPERTY_RECOMMENDATION
COST_ESTIMATION
DESIGN
GENERAL_REAL_ESTATE_QUERY
PLATFORM_HELP
DEALER_CHAT

However, AI routing must not bypass backend authorization.

For example:

AI:
"User wants admin data."

Backend:
"User is not an admin."

Result:
Access denied.

AI intent detection never grants permission.

5.6 AI Prompt Security

System prompts and internal instructions must not be exposed to users.

The AI must not be instructed to reveal:

System prompts
Internal architecture
Secrets
Authentication credentials
Internal database information
5.7 AI Failure Handling

If Ollama or the selected model is unavailable:

AI Service
   ↓
Failure
   ↓
Backend catches error
   ↓
Log technical error
   ↓
Return safe response
   ↓
Frontend displays friendly message
6. General Rules
6.1 Code Style

Code must be:

Readable
Consistent
Modular
Maintainable
Explicit where necessary
Free of unnecessary complexity

Prefer simple solutions over clever solutions.

6.2 Python Style

Follow standard Python conventions.

Use:

snake_case

for:

Variables
Functions
Modules

Use:

PascalCase

for:

Classes
Pydantic models

Examples:

user_profile
get_property()
PropertyService
PropertyCreate
6.3 React Naming

Components:

PascalCase

Examples:

PropertyCard.jsx
ChatWindow.jsx
AdminDashboard.jsx

Functions and variables:

camelCase

Examples:

getProperties()
handleLogin()
propertyData
6.4 File Naming

Frontend components:

PascalCase.jsx

Backend Python files:

snake_case.py

Documentation:

kebab-case.md

Examples:

PropertyCard.jsx
property_service.py
cost-estimation.md
6.5 Constants

Constants should use uppercase naming where appropriate.

Example:

MAX_PROPERTY_IMAGES = 20
DEFAULT_PAGE_SIZE = 20
6.6 API Naming

Use REST-style resource names.

Preferred:

GET    /api/properties
GET    /api/properties/{id}
POST   /api/properties
PUT    /api/properties/{id}
DELETE /api/properties/{id}

Avoid inconsistent endpoint naming.

6.7 Database Naming

Use consistent snake_case.

Examples:

user_id
property_id
created_at
updated_at
dealer_id

Tables should use a consistent naming convention throughout the project.

6.8 Date and Time

Store timestamps consistently.

Prefer UTC internally.

Convert timestamps to the user's local timezone at the presentation layer when required.

6.9 API Versioning

If API versioning becomes necessary, use:

/api/v1/

Example:

/api/v1/properties
/api/v1/auth/login

Do not introduce versioning inconsistently.

6.10 Commit Messages

Use clear and meaningful commit messages.

Preferred format:

type: short description

Examples:

feat: add user authentication
feat: add property search
feat: add dealer chat
feat: integrate ollama chatbot
fix: resolve property filtering issue
fix: prevent unauthorized admin access
refactor: simplify property service
docs: update architecture documentation
test: add authentication tests
chore: update dependencies

Allowed types:

feat
fix
refactor
docs
test
chore
perf
security

Do not use meaningless messages such as:

update
changes
final
final2
new
working
test
6.11 Commit Size

Prefer small, logically grouped commits.

Bad:

"Build entire website"

Good:

feat: add authentication backend
feat: add login interface
feat: add property model
feat: add property search API
6.12 Security Rules

Security is mandatory.

Never commit:
.env
API keys
Passwords
JWT secrets
Database credentials
Private certificates
Private tokens
Authentication
Passwords must be securely hashed.
Authentication tokens must be protected.
Sessions/tokens must have appropriate expiration.
Logout must invalidate or appropriately clear authentication state.
Authorization

Always verify permissions on the backend.

Example:

Dealer A
   ↓
Attempts to modify Dealer B's property
   ↓
Backend checks ownership
   ↓
403 Forbidden
6.13 Data Privacy

Only collect information necessary for the application's functionality.

Do not unnecessarily store:

Sensitive personal information
Authentication credentials
Private conversations
Unnecessary tracking information

User data must only be accessible to authorized users.

Users should not be able to retrieve another user's private data by manipulating IDs or API requests.

6.14 Input Security

Treat all external input as untrusted.

Validate:

Forms
API requests
Query parameters
File uploads
Chat input
Property data
User profile information

Protect against common attacks including:

SQL injection
XSS
CSRF where applicable
Broken access control
Malicious file uploads
Prompt injection affecting privileged actions
6.15 File Uploads

If property/design images are supported:

Validate file type.
Validate file size.
Generate safe filenames.
Do not trust user-provided filenames.
Do not execute uploaded files.
Store uploads outside executable source directories.
Restrict allowed formats.
6.16 Performance Rules

The system should remain responsive as data grows.

Use:

Pagination
Database indexes
Efficient queries
Lazy loading
Image optimization
API response limits
Appropriate caching where needed

Avoid:

Loading entire property databases into the frontend.
Unnecessary database queries.
Repeated API requests.
Large unoptimized images.
Expensive calculations on every page render.
6.17 Scalability Rules

The architecture should support future growth.

Design modules with clear boundaries.

Avoid tightly coupling:

AI
Property
Chat
Design
Admin

Each module should have a clear responsibility.

6.18 Frontend Performance

Prefer:

Lazy loading
Code splitting
Pagination
Memoization where justified
Optimized images
Reusable components

Do not use optimization techniques without a reason.

Premature optimization should be avoided.

6.19 Backend Performance

Use:

Database indexes
Efficient queries
Pagination
Connection pooling
Async I/O where appropriate
Proper resource management

Avoid N+1 database query patterns.

6.20 Comment Standard

Comments should explain why, not simply what.

Good:

# Use a database transaction here because creating the dealer
# and initial property profile must succeed or fail together.

Bad:

# Create dealer
dealer = create_dealer()

Use comments for:

Complex algorithms
Non-obvious decisions
Security constraints
Temporary workarounds
External service limitations
6.21 Documentation Standard

Any significant architectural or behavioral change must update the appropriate documentation.

Examples:

Authentication change
→ authentication.md

Database change
→ database.md

API change
→ api.md

AI behavior change
→ ai.md

Architecture change
→ architecture.md
6.22 Testing Rules

Every major feature must have appropriate tests.

Minimum expectations:

Authentication

Test:

Signup
Login
Invalid credentials
Duplicate account
Unauthorized access
Token/session behavior
Properties

Test:

Create
Read
Update
Delete
Search
Filtering
Authorization
Chat

Test:

Conversation creation
Message creation
Access control
Unauthorized conversation access
AI

Test:

Request handling
AI service availability
Invalid input
Failure fallback
Intent routing where implemented
Admin

Test:

Admin authentication
Admin authorization
Unauthorized user access
Administrative operations
6.23 Test Before Commit

Before committing significant code:

1. Run formatter/linter
2. Run relevant tests
3. Check application startup
4. Check API behavior
5. Review changed files
6. Check for secrets
7. Commit
6.24 Regression Testing

When modifying an existing feature, verify that related functionality still works.

Example:

Changing authentication should trigger checks for:

Login
Signup
User routes
Dealer routes
Admin routes
Protected APIs
Logout
6.25 Development Workflow

The preferred workflow is:

Understand Requirement
        ↓
Read Relevant Documentation
        ↓
Inspect Existing Code
        ↓
Plan Implementation
        ↓
Implement Small Change
        ↓
Run Tests
        ↓
Review Code
        ↓
Update Documentation
        ↓
Commit

Do not immediately rewrite large parts of the application without first understanding the existing implementation.

6.26 AI Coding Agent Rules

Claude Code and other AI coding agents must:

Read CLAUDE.md.
Read relevant documentation.
Inspect existing code before modifying it.
Follow architecture.md.
Follow this rules.md.
Avoid introducing unapproved technologies.
Avoid unnecessary dependencies.
Never expose secrets.
Never weaken authentication or authorization.
Run appropriate tests after changes.
Explain significant architectural changes.
Update documentation when required.
Do not delete existing functionality without explicit approval.
Do not rewrite working modules unnecessarily.
Ask for clarification when requirements conflict rather than making a major assumption.
6.27 Rule for Existing Code

Existing working code should be preserved unless there is a clear reason to modify it.

Before replacing a module:

Inspect
 ↓
Understand
 ↓
Identify problem
 ↓
Determine smallest safe change
 ↓
Implement
 ↓
Test

Do not rewrite code merely to match personal coding preferences.

6.28 Rule for New Dependencies

Before adding a new package, answer:

1. Why is it needed?
2. Can existing dependencies solve the problem?
3. Is it compatible with the architecture?
4. Is it maintained?
5. Does it introduce security risks?
6. Does it increase unnecessary complexity?

If the answer is unclear, do not add it automatically.

6.29 Rule for Architectural Changes

Any major architectural change must be documented.

Examples:

Changing PostgreSQL
Adding Redis
Changing FastAPI architecture
Introducing WebSockets
Adding another AI provider
Adding microservices
Changing authentication
Changing storage architecture

The change should be reflected in:

architecture.md
rules.md
relevant module documentation
6.30 Rule for Production Readiness

Before deployment, verify:

[ ] No secrets committed
[ ] Debug mode disabled
[ ] Authentication working
[ ] Authorization working
[ ] Database migrations applied
[ ] Error handling implemented
[ ] Logging configured
[ ] API validation implemented
[ ] Frontend production build succeeds
[ ] Backend starts successfully
[ ] Docker build succeeds
[ ] Tests pass
[ ] Environment variables configured
[ ] Sensitive data protected
7. Project-Specific Rules

The following rules are specific to this AI-powered real-estate platform.

7.1 Property Data

AI must not invent property listings.

Property information must come from the application's database or another explicitly trusted data source.

7.2 Property Recommendations

Recommendations should be based on actual available property data.

The system must not recommend a property that does not exist in the platform's dataset.

7.3 Construction Cost

Construction cost estimates must be clearly labeled as estimates.

The system must not represent an AI-generated estimate as a guaranteed market quotation.

7.4 Dealer Communication

Users may only access conversations they are authorized to access.

Dealers may only access conversations involving them.

Admins may have broader access according to the defined administrative policy.

7.5 Admin Access

Admin access must require:

Authentication
+
Admin Role
+
Backend Authorization

A hidden frontend button is not sufficient protection.

7.6 AI and Admin Permissions

AI must never grant administrative permissions.

The following is invalid:

User → AI → Admin Action

The backend must independently verify authorization.

7.7 AI and Database

The AI must not directly execute unrestricted database queries.

AI-generated actions must pass through controlled backend services.

7.8 AI and Code Execution

The user-facing AI must not have unrestricted access to:

Operating system
Shell
Filesystem
Database
Application source code

Any future tool-use capability must be explicitly designed, restricted, validated, and authorized.

7.9 Design Modules

The 2D, 3D, and interior design modules should remain modular.

Changing the design rendering implementation should not require rewriting authentication, property management, or the admin system.

8. Rule Priority

If two rules conflict, follow this priority:

1. Security
2. Data integrity
3. Functional requirements
4. Architecture
5. Maintainability
6. Performance
7. Developer convenience

Security and data integrity always take priority over convenience.

9. Final Engineering Principle

The project should follow this principle:

Build the simplest secure, maintainable, testable solution that satisfies the requirement while remaining consistent with the approved architecture.

The goal is not to use the maximum number of technologies.

The goal is to build a reliable, understandable, modular, and scalable system.


### One important point

I recommend putting this file at:

```text
your-project/
├── CLAUDE.md
├── docs/
│   ├── PRD.md
│   ├── architecture.md
│   └── rules.md       ← this file

And make CLAUDE.md explicitly tell Claude Code:

Before modifying the project, read:
1. docs/PRD.md
2. docs/architecture.md
3. docs/rules.md
4. The relevant module documentation