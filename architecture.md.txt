# AI-Powered Real Estate Platform

## System Architecture Documentation

**Document:** `architecture.md`
**Version:** 1.0
**Project Type:** Final Year Project
**Architecture Style:** Modular Full-Stack Architecture
**Frontend:** React + Tailwind CSS
**Backend:** FastAPI
**Database:** PostgreSQL
**AI Runtime:** Ollama
**Containerization:** Docker

---

# 1. Architecture

## 1.1 System Overview

The AI-Powered Real Estate Platform is a modular full-stack web application that integrates real-estate services into a single platform.

The system consists of:

* React frontend
* Tailwind CSS UI layer
* FastAPI backend
* PostgreSQL database
* Authentication and authorization system
* Property management system
* Dealer management system
* User–dealer communication system
* AI chatbot
* Ollama AI service
* Property recommendation module
* 2D design module
* 3D design module
* Interior design module
* Construction cost estimation module
* Admin management system

The architecture follows a layered and modular approach.

```text
┌───────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                          │
│                                                           │
│                 React + Tailwind CSS                      │
│                                                           │
│  Pages │ Components │ Forms │ Chat │ Design │ Dashboard    │
└──────────────────────────┬────────────────────────────────┘
                           │
                           │ HTTP/REST API
                           ▼
┌───────────────────────────────────────────────────────────┐
│                     API LAYER                             │
│                                                           │
│                       FastAPI                             │
│                                                           │
│ Auth │ Users │ Dealers │ Properties │ Chat │ AI │ Admin   │
└──────────────────────────┬────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────┐
│                  BUSINESS LOGIC LAYER                     │
│                                                           │
│ Authentication │ Property │ Recommendation │ Design       │
│ Cost Estimation │ Chat │ AI │ Administration              │
└───────────────┬─────────────────────────┬─────────────────┘
                │                         │
                ▼                         ▼
┌───────────────────────────┐    ┌───────────────────────────┐
│      DATA LAYER           │    │       AI LAYER            │
│                           │    │                           │
│      PostgreSQL           │    │          Ollama           │
│                           │    │                           │
│ Users                     │    │ AI Chatbot                │
│ Dealers                   │    │ Intent Detection          │
│ Properties                │    │ Request Routing           │
│ Chats                     │    │ AI Responses              │
│ Messages                  │    │                           │
│ Designs                   │    │                           │
│ Recommendations           │    │                           │
└───────────────────────────┘    └───────────────────────────┘
```

---

# 1.2 Architectural Principles

The project must follow these principles:

### Separation of Concerns

Each layer has a specific responsibility.

```text
Frontend
→ Presentation

Backend
→ Business Logic + API

Database
→ Persistent Data

AI Service
→ AI Processing
```

### Modularity

Each major feature should be implemented as an independent module.

### Reusability

Reusable frontend components and backend services should be preferred over duplicated code.

### Security

Authentication, authorization, validation, and secret management must be handled from the beginning.

### Maintainability

Code should be organized so that another developer can understand and modify the project.

### Scalability

The system should be capable of adding new modules without requiring major changes to existing modules.

### API-First Communication

Frontend modules should communicate with backend functionality through documented APIs.

---

# 1.3 System Layers

## Layer 1 — Presentation Layer

Implemented using:

* React
* Tailwind CSS

Responsibilities:

* Display UI
* Handle user interaction
* Client-side validation
* Navigation
* Form handling
* Display loading states
* Display errors
* Send API requests
* Display API responses

The frontend must not contain sensitive secrets or enforce security-critical authorization by itself.

---

## Layer 2 — API Layer

Implemented using:

* FastAPI
* REST APIs

Responsibilities:

* Receive HTTP requests
* Validate requests
* Authenticate users
* Authorize users
* Call business services
* Return structured responses

Example:

```text
POST /api/auth/login
GET /api/properties
GET /api/properties/{id}
POST /api/properties
POST /api/ai/chat
GET /api/chats
POST /api/chats/{id}/messages
```

---

## Layer 3 — Business Logic Layer

This layer contains the actual application rules.

Examples:

```text
Authentication Service
Property Service
Dealer Service
Recommendation Service
Cost Estimation Service
Chat Service
AI Service
Admin Service
Design Service
```

Business logic should not be unnecessarily placed inside API route handlers.

---

## Layer 4 — Data Access Layer

The data access layer communicates with PostgreSQL.

Responsibilities:

* Create records
* Retrieve records
* Update records
* Delete records
* Execute queries
* Handle relationships
* Apply database-level constraints

The rest of the application should not directly manipulate the database unnecessarily.

---

## Layer 5 — AI Layer

The AI layer communicates with Ollama.

Responsibilities:

* Process chatbot requests
* Generate responses
* Analyze user intent
* Route requests where appropriate
* Provide AI-assisted functionality

The frontend must communicate with the AI through the backend rather than directly connecting to Ollama.

```text
React
 ↓
FastAPI
 ↓
AI Service
 ↓
Ollama
 ↓
Model
```

---

# 1.4 Major System Components

## A. Authentication Module

Responsible for:

* User registration
* Login
* Logout
* Password hashing
* Authentication
* Session/token management
* User identity

---

## B. Authorization Module

Responsible for determining what each role can access.

Roles:

```text
Visitor
User
Dealer
Admin
```

Example:

```text
User
 ├── Search properties
 ├── Recommendations
 ├── AI chatbot
 ├── Cost estimation
 └── Chat with dealer

Dealer
 ├── Manage own properties
 └── Chat with users

Admin
 ├── Manage users
 ├── Manage dealers
 ├── Manage properties
 └── Manage platform
```

Authorization must be enforced on the backend.

---

# 1.5 Property Module

The property module manages property listings.

Responsibilities:

* Create property
* Read property
* Update property
* Delete property
* Search properties
* Filter properties
* View property details
* Associate properties with dealers
* Store property images

Basic flow:

```text
User
 ↓
Property Search
 ↓
Frontend
 ↓
GET /api/properties
 ↓
FastAPI
 ↓
Property Service
 ↓
Database
 ↓
Properties
 ↓
Frontend
```

---

# 1.6 Dealer Module

The dealer module manages dealer accounts and their property listings.

Responsibilities:

* Dealer profile
* Dealer authentication
* Property management
* Customer inquiries
* User communication

A dealer should only be able to modify resources they are authorized to manage.

---

# 1.7 User Module

The user module manages registered users.

Responsibilities:

* User profile
* Account information
* User preferences
* User activity
* Saved/relevant property data where implemented

---

# 1.8 User–Dealer Chat Module

This module provides communication between users and dealers.

Architecture:

```text
User
 ↓
Chat Interface
 ↓
React
 ↓
FastAPI
 ↓
Chat Service
 ↓
Database
 ↓
Message
 ↓
Dealer
```

The system must ensure that users can only access conversations they are authorized to access.

The same applies to dealers.

Real-time communication using WebSockets may be added if required. The initial implementation can use REST APIs if real-time communication is not required.

---

# 1.9 AI Chatbot Module

The AI chatbot is a centralized interface.

Architecture:

```text
User
 ↓
AI Chat Interface
 ↓
React
 ↓
POST /api/ai/chat
 ↓
FastAPI
 ↓
AI Service
 ↓
Ollama
 ↓
Language Model
 ↓
AI Response
 ↓
React
 ↓
User
```

The AI module should be independent of the frontend.

---

# 1.10 AI Intent and Routing

The chatbot may identify the user's intent and route requests to the appropriate system functionality.

Conceptual architecture:

```text
                 User Question
                       │
                       ▼
                AI Chatbot
                       │
                       ▼
                 Intent Layer
                       │
       ┌───────────────┼────────────────┐
       │               │                │
       ▼               ▼                ▼
    Property         Design           Cost
     Search          Module         Estimation
       │               │                │
       └───────────────┼────────────────┘
                       │
                       ▼
                    Response
```

Examples:

```text
"Find houses under 10 million"
        ↓
Property Search

"Estimate construction cost"
        ↓
Cost Estimation

"Help me design a 5 marla house"
        ↓
Design Module

"Which property is suitable for me?"
        ↓
Recommendation Module
```

The routing implementation should be kept modular so the AI system can be improved independently.

---

# 1.11 Property Recommendation Module

The recommendation module receives user requirements and produces relevant property recommendations.

Potential inputs:

```text
Budget
Location
Property Type
Area
Bedrooms
Bathrooms
Preferences
```

Flow:

```text
User Preferences
       ↓
Recommendation API
       ↓
Recommendation Service
       ↓
Property Data
       ↓
Filtering / Ranking
       ↓
Recommended Properties
```

The first implementation may use rule-based filtering/ranking.

A machine-learning recommendation system can be introduced later.

---

# 1.12 Construction Cost Estimation Module

The module calculates estimated construction costs.

Possible inputs:

```text
Location
Covered Area
Number of Floors
Construction Quality
Material Quality
Additional Features
```

Flow:

```text
User Input
 ↓
Frontend Validation
 ↓
FastAPI
 ↓
Cost Estimation Service
 ↓
Calculation Engine
 ↓
Estimated Cost
 ↓
Frontend
```

Rates and configuration values should preferably be stored in configurable data rather than scattered hardcoded values.

The result must be presented as an estimate rather than a guaranteed construction quotation.

---

# 1.13 2D Design Module

The 2D design module provides two-dimensional layout functionality.

Potential features:

* Floor plans
* Rooms
* Dimensions
* Doors
* Windows
* Layout editing
* Save/load design

The design engine should remain modular.

---

# 1.14 3D Design Module

The 3D design module provides three-dimensional visualization.

Potential functionality:

* 3D rooms
* Property structure
* Furniture/architectural elements
* Dimensions
* Navigation
* Save/load design

The 3D rendering implementation should remain isolated from core backend functionality.

---

# 1.15 Interior Design Module

The interior design module provides interior-space visualization.

Potential functionality:

* Furniture
* Colors
* Materials
* Interior styles
* Layout
* Visualization
* Save/load designs

AI-based interior design functionality may be integrated later through the AI layer.

---

# 1.16 Admin Module

The admin module provides centralized platform management.

Architecture:

```text
Admin
 ↓
Admin Login
 ↓
Authentication
 ↓
Role Verification
 ↓
Admin Dashboard
 ↓
Admin APIs
 ↓
Database
```

Possible administrative functionality:

```text
Users
Dealers
Properties
Reports
System Statistics
Platform Management
```

Admin APIs must perform backend authorization checks.

Hiding an admin button in the frontend is not considered sufficient security.

---

# 1.17 Database Architecture

The core database should contain entities such as:

```text
users
dealers
properties
property_images
chats
messages
designs
cost_estimates
recommendations
```

Basic relationships:

```text
User
 │
 ├───────────────┐
 │               │
 ▼               ▼
Chat            Recommendation
 │
 ▼
Message
 │
 ▼
Dealer
 │
 ▼
Property
```

A dealer may have multiple properties.

A user may have multiple conversations.

A conversation contains multiple messages.

Foreign keys must maintain referential integrity.

---

# 1.18 Request Lifecycle

Every normal application request should follow:

```text
User Action
    ↓
React Component
    ↓
Frontend Validation
    ↓
HTTP Request
    ↓
FastAPI Router
    ↓
Authentication
    ↓
Authorization
    ↓
Request Validation
    ↓
Business Service
    ↓
Repository/Data Access
    ↓
PostgreSQL
    ↓
Response
    ↓
React State
    ↓
UI Update
```

AI request lifecycle:

```text
User
 ↓
React Chat
 ↓
FastAPI
 ↓
Authentication
 ↓
AI Service
 ↓
Ollama
 ↓
AI Model
 ↓
AI Response
 ↓
FastAPI
 ↓
React
 ↓
User
```

---

# 1.19 Security Architecture

Security is applied at multiple layers.

```text
Frontend
   ↓
Backend Authentication
   ↓
Backend Authorization
   ↓
Input Validation
   ↓
Business Logic
   ↓
Database
```

Important rules:

* Passwords must never be stored in plain text.
* API keys must never be exposed in frontend code.
* Secrets must be stored using environment variables.
* Backend authorization is mandatory.
* User input must be validated.
* Admin endpoints must be protected.
* Sensitive information must not be exposed in error responses.
* Database access must be controlled.
* Production communication should use HTTPS.

---

# 1.20 Error Handling Architecture

Errors should be handled consistently.

```text
Error
 ↓
Backend Exception Handling
 ↓
Log Technical Information
 ↓
Safe API Response
 ↓
Frontend Error Handler
 ↓
User-Friendly Message
```

The system should distinguish between:

```text
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
422 Validation Error
500 Internal Server Error
```

Internal stack traces must not be exposed to normal users.

---

# 1.21 Performance Architecture

The system should consider performance from the beginning.

Frontend:

* Lazy loading
* Image optimization
* Component reuse
* Efficient state updates
* Code splitting

Backend:

* Pagination
* Database indexes
* Efficient queries
* Connection pooling
* Caching where appropriate

Example:

```text
GET /api/properties?page=1&limit=20
```

instead of returning every property in the database.

---

# 1.22 Scalability Architecture

The initial system should use a **modular monolith** rather than unnecessary microservices.

```text
                FastAPI Application
                       │
       ┌───────────────┼───────────────┐
       │               │               │
      Auth          Property          AI
       │               │               │
      Chat           Dealer         Design
       │               │               │
      Admin       Recommendation     Cost
```

Each module should have clear boundaries.

If the project grows significantly, individual modules can later be separated into independent services.

---

# 2. Folder and File Structure

The project should follow the structure below.

```text
real-estate-platform/
│
├── README.md
├── CLAUDE.md
├── .gitignore
├── .env.example
├── docker-compose.yml
├── docker/
│
├── frontend/
│   │
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   │
│   ├── public/
│   │
│   └── src/
│       │
│       ├── assets/
│       │
│       ├── components/
│       │   ├── common/
│       │   ├── layout/
│       │   ├── property/
│       │   ├── chat/
│       │   ├── design/
│       │   └── admin/
│       │
│       ├── pages/
│       │   ├── auth/
│       │   ├── user/
│       │   ├── dealer/
│       │   ├── admin/
│       │   ├── property/
│       │   ├── design/
│       │   └── chatbot/
│       │
│       ├── layouts/
│       │   ├── PublicLayout.jsx
│       │   ├── UserLayout.jsx
│       │   ├── DealerLayout.jsx
│       │   └── AdminLayout.jsx
│       │
│       ├── services/
│       │   ├── api.js
│       │   ├── authService.js
│       │   ├── propertyService.js
│       │   ├── dealerService.js
│       │   ├── chatService.js
│       │   ├── aiService.js
│       │   └── recommendationService.js
│       │
│       ├── hooks/
│       │
│       ├── context/
│       │   ├── AuthContext.jsx
│       │   └── AppContext.jsx
│       │
│       ├── routes/
│       │   └── AppRoutes.jsx
│       │
│       ├── utils/
│       │
│       ├── constants/
│       │
│       ├── App.jsx
│       └── main.jsx
│
├── backend/
│   │
│   ├── requirements.txt
│   ├── Dockerfile
│   │
│   ├── app/
│   │   │
│   │   ├── main.py
│   │   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── database.py
│   │   │
│   │   ├── api/
│   │   │   └── router.py
│   │   │
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── dealer.py
│   │   │   ├── property.py
│   │   │   ├── chat.py
│   │   │   ├── message.py
│   │   │   └── design.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── dealer.py
│   │   │   ├── property.py
│   │   │   ├── chat.py
│   │   │   ├── ai.py
│   │   │   └── recommendation.py
│   │   │
│   │   ├── repositories/
│   │   │   ├── user_repository.py
│   │   │   ├── property_repository.py
│   │   │   ├── dealer_repository.py
│   │   │   └── chat_repository.py
│   │   │
│   │   ├── services/
│   │   │   ├── auth_service.py
│   │   │   ├── user_service.py
│   │   │   ├── dealer_service.py
│   │   │   ├── property_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── ai_service.py
│   │   │   ├── recommendation_service.py
│   │   │   └── cost_estimation_service.py
│   │   │
│   │   └── modules/
│   │       │
│   │       ├── auth/
│   │       ├── users/
│   │       ├── dealers/
│   │       ├── properties/
│   │       ├── chat/
│   │       ├── ai/
│   │       ├── recommendations/
│   │       ├── design/
│   │       ├── cost_estimation/
│   │       └── admin/
│   │
│   └── tests/
│       ├── test_auth.py
│       ├── test_properties.py
│       ├── test_chat.py
│       ├── test_ai.py
│       └── test_admin.py
│
├── database/
│   ├── migrations/
│   ├── seed/
│   └── schema/
│
├── docs/
│   ├── PRD.md
│   ├── architecture.md
│   ├── requirements.md
│   ├── database.md
│   ├── api.md
│   ├── authentication.md
│   ├── authorization.md
│   ├── ai.md
│   ├── chat.md
│   ├── admin.md
│   ├── design.md
│   ├── cost-estimation.md
│   ├── recommendation.md
│   ├── testing.md
│   ├── deployment.md
│   └── coding-rules.md
│
└── tests/
    └── integration/
```

---

# 2.1 Root Files

## `README.md`

The main documentation for developers.

It should contain:

* Project overview
* Features
* Tech stack
* Installation
* Environment setup
* Running the application
* Docker instructions
* Development instructions

---

## `CLAUDE.md`

Instructions for Claude Code or other AI coding agents.

It should contain:

* Project purpose
* Architecture rules
* Coding conventions
* Technology choices
* Important constraints
* Development workflow
* Rules for modifying existing code

`CLAUDE.md` is an AI-development instruction file and should reference the detailed documentation inside `docs/`.

---

## `.env.example`

Contains the names of required environment variables without real secrets.

Example:

```text
DATABASE_URL=
JWT_SECRET=
OLLAMA_URL=
APP_ENV=
```

---

## `.gitignore`

Prevents unnecessary or sensitive files from entering Git.

It should include:

```text
.env
node_modules/
__pycache__/
.venv/
dist/
build/
*.log
```

---

## `docker-compose.yml`

Defines the development services.

Potential services:

```text
frontend
backend
database
ollama
```

The final service configuration depends on the deployment requirements.

---

# 2.2 Frontend Structure

The frontend is responsible only for presentation, interaction, client-side state, and communication with backend APIs.

## `components/`

Contains reusable UI components.

Example:

```text
components/
├── common/
│   ├── Button.jsx
│   ├── Input.jsx
│   ├── Modal.jsx
│   ├── Loading.jsx
│   └── ErrorMessage.jsx
│
├── layout/
│   ├── Navbar.jsx
│   ├── Sidebar.jsx
│   └── Footer.jsx
│
├── property/
│   ├── PropertyCard.jsx
│   ├── PropertyGrid.jsx
│   └── PropertyFilters.jsx
│
└── chat/
    ├── ChatWindow.jsx
    ├── MessageBubble.jsx
    └── ChatInput.jsx
```

---

## `pages/`

Contains complete application pages.

Examples:

```text
pages/
├── auth/
│   ├── Login.jsx
│   └── Signup.jsx
│
├── user/
│   └── Dashboard.jsx
│
├── dealer/
│   └── DealerDashboard.jsx
│
├── admin/
│   └── AdminDashboard.jsx
│
├── property/
│   ├── PropertySearch.jsx
│   └── PropertyDetails.jsx
│
└── chatbot/
    └── Chatbot.jsx
```

---

## `services/`

Contains frontend API communication.

Example:

```text
authService.js
propertyService.js
dealerService.js
chatService.js
aiService.js
recommendationService.js
```

API calls should be centralized here rather than scattered throughout components.

---

## `context/`

Contains global frontend state where required.

Examples:

```text
AuthContext.jsx
AppContext.jsx
```

---

## `routes/`

Defines frontend navigation and protected routes.

Examples:

```text
Public Routes
User Routes
Dealer Routes
Admin Routes
```

Frontend route protection improves UX, but backend authorization remains the actual security mechanism.

---

# 2.3 Backend Structure

The backend is responsible for:

* APIs
* Authentication
* Authorization
* Business logic
* Database operations
* AI integration
* Validation
* Error handling

---

## `main.py`

Application entry point.

Responsibilities:

* Initialize FastAPI
* Register routers
* Configure middleware
* Configure application startup/shutdown behavior

---

## `core/`

Contains core infrastructure.

```text
core/
├── config.py
├── security.py
└── database.py
```

### `config.py`

Application configuration and environment variables.

### `security.py`

Authentication-related security functions.

### `database.py`

Database connection and session configuration.

---

## `models/`

Contains database models.

Examples:

```text
User
Dealer
Property
Chat
Message
Design
```

---

## `schemas/`

Contains request and response schemas.

Schemas define what data APIs accept and return.

Example:

```text
PropertyCreate
PropertyUpdate
PropertyResponse
LoginRequest
LoginResponse
```

---

## `repositories/`

Handles database access.

Repositories should isolate database queries from business logic.

---

## `services/`

Contains business logic.

For example:

```text
property_service.py
```

may handle:

```text
Create Property
Update Property
Delete Property
Search Property
Validate Dealer Ownership
```

---

# 2.4 Documentation Structure

The `docs/` directory is the project's knowledge base.

```text
docs/
│
├── PRD.md
├── architecture.md
├── requirements.md
├── database.md
├── api.md
├── authentication.md
├── authorization.md
├── ai.md
├── chat.md
├── admin.md
├── design.md
├── cost-estimation.md
├── recommendation.md
├── testing.md
├── deployment.md
└── coding-rules.md
```

Each document should have one clear responsibility.

---

# 3. Tech Stack

## 3.1 Frontend

### React

React is used to build the application's component-based user interface.

Purpose:

* UI development
* Component architecture
* State-driven rendering
* Application pages
* Interactive functionality

---

### Tailwind CSS

Tailwind CSS is used for styling.

Purpose:

* Responsive design
* Consistent UI
* Reusable styling
* Rapid frontend development

---

### JavaScript

JavaScript is used as the primary frontend programming language.

---

### React Router

Used for frontend navigation.

Responsibilities:

* Public routes
* User routes
* Dealer routes
* Admin routes
* Protected navigation

---

# 3.2 Backend

## Python

Python is the backend programming language.

---

## FastAPI

FastAPI is the primary backend framework.

Responsibilities:

* REST APIs
* Request validation
* Authentication integration
* Business logic integration
* AI service integration
* Database integration

---

# 3.3 Database

## PostgreSQL

PostgreSQL is the recommended relational database.

It stores:

* Users
* Dealers
* Properties
* Messages
* Chats
* Designs
* Recommendations
* Cost estimates
* Other persistent application data

---

# 3.4 AI

## Ollama

Ollama will serve as the AI model runtime for the centralized chatbot.

Architecture:

```text
FastAPI
   ↓
AI Service
   ↓
Ollama
   ↓
Language Model
```

The exact model used with Ollama should be selected according to available hardware, performance requirements, and project requirements.

---

# 3.5 API Communication

The frontend communicates with the backend through HTTP/REST APIs.

Conceptually:

```text
React
  │
  │ HTTP/JSON
  ▼
FastAPI
  │
  ▼
Services
  │
  ▼
Database / Ollama
```

---

# 3.6 Containerization

## Docker

Docker will be used to package services into reproducible environments.

Potential containers:

```text
Frontend
Backend
PostgreSQL
Ollama
```

---

## Docker Compose

Docker Compose can be used to manage multiple development services.

Example:

```text
docker-compose.yml

frontend
backend
database
ollama
```

---

# 3.7 Version Control

## Git

Git will be used for:

* Version control
* Branch management
* Collaboration
* Rollbacks
* Feature development

Recommended branches:

```text
main
develop
feature/authentication
feature/properties
feature/chat
feature/ai
feature/admin
```

---

# 3.8 Testing

The project should use appropriate testing tools for both frontend and backend.

Backend testing should cover:

* Authentication
* Authorization
* APIs
* Business logic
* Database interactions

Frontend testing should cover:

* Components
* Forms
* User interactions
* Important application flows

Integration testing should verify communication between major system components.

---

# 3.9 Environment Configuration

Environment-specific values should be controlled through environment variables.

Examples:

```text
DATABASE_URL
JWT_SECRET
OLLAMA_URL
APP_ENV
```

Secrets must never be hardcoded into source code.

---

# 3.10 Technology Summary

| Layer             | Technology              | Purpose                        |
| ----------------- | ----------------------- | ------------------------------ |
| Frontend          | React                   | User interface                 |
| Styling           | Tailwind CSS            | Responsive UI                  |
| Frontend Language | JavaScript              | Frontend logic                 |
| Routing           | React Router            | Client-side navigation         |
| Backend           | FastAPI                 | REST API and server            |
| Backend Language  | Python                  | Backend development            |
| Database          | PostgreSQL              | Persistent data                |
| AI Runtime        | Ollama                  | Local AI model serving         |
| API               | REST/JSON               | Frontend-backend communication |
| Containers        | Docker                  | Application containerization   |
| Orchestration     | Docker Compose          | Multi-container development    |
| Version Control   | Git                     | Source control                 |
| Testing           | Python/JS testing tools | Automated testing              |

---

# 4. Architecture Rules for Developers and AI Agents

The following rules are mandatory unless the architecture is intentionally changed and documented.

## Rule 1 — Do not mix frontend and backend responsibilities.

React handles presentation.

FastAPI handles business logic and APIs.

---

## Rule 2 — Do not put secrets in frontend code.

API keys, database credentials, JWT secrets, and other sensitive values belong on the backend/environment configuration.

---

## Rule 3 — Backend authorization is mandatory.

Frontend route protection is not a security mechanism.

---

## Rule 4 — Use reusable components.

Do not duplicate UI components unnecessarily.

---

## Rule 5 — Keep business logic out of UI components.

Business rules belong in backend services or appropriate application services.

---

## Rule 6 — Keep database access isolated.

Use repositories/data-access functions rather than scattering database queries throughout the application.

---

## Rule 7 — Validate all backend input.

Never trust input merely because the frontend validated it.

---

## Rule 8 — Keep modules independent.

A change to the chatbot should not unnecessarily break property management.

---

## Rule 9 — Follow the existing folder structure.

Do not create random folders when an appropriate existing location exists.

---

## Rule 10 — Update documentation when architecture changes.

If a developer changes:

* Database structure
* API contracts
* Authentication
* Module boundaries
* Technology
* Folder architecture

the relevant documentation must also be updated.

---

## Rule 11 — Do not over-engineer.

The project should initially use a modular monolithic architecture.

Microservices should only be introduced if there is a demonstrated requirement.

---

## Rule 12 — Inspect before modifying.

Before making a significant change, developers and AI coding agents should inspect the existing implementation and relevant documentation.

They should not assume that a file, service, endpoint, or component does not already exist.

---

# 5. Source of Truth Hierarchy

When developing the project, use the following hierarchy:

```text
PRD
 │
 ├── Defines WHAT the product must do
 │
 ▼
architecture.md
 │
 ├── Defines HOW the system is structured
 │
 ▼
Module Documentation
 │
 ├── Defines HOW individual features work
 │
 ▼
Source Code
 │
 └── Actual implementation
```

For AI coding agents:

```text
CLAUDE.md
     ↓
architecture.md
     ↓
Relevant module documentation
     ↓
Existing source code
     ↓
Implementation
```

The AI agent must inspect existing source code before making assumptions about implementation.

---

# 6. Final Architecture

The final high-level architecture is:

```text
                           USERS
                             │
                             ▼
                  ┌────────────────────┐
                  │   React Frontend   │
                  │   Tailwind CSS     │
                  └─────────┬──────────┘
                            │
                         REST API
                            │
                            ▼
                  ┌────────────────────┐
                  │   FastAPI Backend  │
                  └─────────┬──────────┘
                            │
       ┌────────────────────┼─────────────────────┐
       │                    │                     │
       ▼                    ▼                     ▼
 ┌──────────┐        ┌─────────────┐       ┌────────────┐
 │   Auth   │        │   Business  │       │ AI Service │
 │          │        │   Modules   │       │            │
 └──────────┘        └──────┬──────┘       └──────┬─────┘
                            │                     │
             ┌──────────────┼─────────────┐       ▼
             │              │             │     Ollama
             ▼              ▼             ▼
        Properties       Chat         Design
             │              │             │
             └──────────────┼─────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │   PostgreSQL  │
                    └───────────────┘
```

This architecture should be treated as the **baseline architecture** for the project.

Any major architectural change should be discussed, justified, implemented carefully, and reflected in the documentation.
