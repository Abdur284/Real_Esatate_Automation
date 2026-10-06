# AI-Powered Real Estate Platform
## Development Phases Documentation

**Document:** `phase.doc.md`
**Version:** 1.0
**Project Type:** Final Year Project
**Architecture:** Modular Full-Stack Architecture
**Frontend:** React + Tailwind CSS
**Backend:** FastAPI
**Database:** PostgreSQL
**AI Runtime:** Ollama
**Containerization:** Docker

---

# 1. Project Development Strategy

The project will be developed in multiple controlled phases.

Each phase must be completed, tested, and documented before moving to the next major phase.

The development strategy is:

```text
Phase 1
Authentication & Authorization
        ↓
Phase 2
Dashboard & Application Layout
        ↓
Phase 3
Core CRUD & Property Management
        ↓
Phase 4
AI + Design + Business Features
        ↓
Phase 5
Testing & Quality Assurance
        ↓
Phase 6
Deployment & Maintenance

The development should follow an incremental approach.

Do not attempt to build the entire project simultaneously.

2. Phase 1 — Login and Authentication
Objective

Implement the complete authentication and authorization foundation for the platform.

This phase establishes the identity and access-control system that all other protected modules will use.

2.1 User Registration

Implement registration for normal users.

Required functionality:

User signup
Name
Email
Password
Password confirmation
Input validation
Duplicate email detection
Secure password hashing
Account creation
Appropriate success/error messages

Example flow:

User
 ↓
Signup Form
 ↓
Frontend Validation
 ↓
FastAPI API
 ↓
Pydantic Validation
 ↓
Password Hashing
 ↓
PostgreSQL
 ↓
User Created
2.2 User Login

Implement secure login.

Requirements:

Email/username validation
Password verification
Authentication token/session creation
Invalid credential handling
Login error messages
Protected route access

Flow:

Login
 ↓
FastAPI
 ↓
Find User
 ↓
Verify Password
 ↓
Generate Authentication Token
 ↓
Authenticated User
2.3 Logout

Implement logout functionality.

Requirements:

Clear authentication state.
Remove/expire client-side authentication information as appropriate.
Redirect user to the appropriate public page.
Prevent access to protected frontend pages after logout.
2.4 Password Reset

If included in the final project scope, implement:

Forgot password
Password reset request
Reset token
New password
Password confirmation
Token expiration
Secure password update

The implementation must not expose whether sensitive account information exists beyond the intended security policy.

2.5 Authentication

The system must establish authentication for:

Visitor
User
Dealer
Admin

Authentication should be handled centrally rather than implemented separately inside every module.

2.6 Authorization

Implement Role-Based Access Control (RBAC).

Roles:

VISITOR
USER
DEALER
ADMIN

Example permissions:

Visitor

Can:

Browse public pages.
View publicly available properties.
Use allowed public functionality.

Cannot:

Access private user information.
Access dealer dashboard.
Access admin dashboard.
User

Can:

Manage own profile.
Search properties.
View property details.
Receive recommendations.
Use AI chatbot.
Use design modules.
Use cost estimation.
Chat with dealers.
Dealer

Can:

Manage own profile.
Create properties.
Update own properties.
Delete own properties.
View customer inquiries.
Chat with users.
Admin

Can:

Manage users.
Manage dealers.
Manage properties.
Monitor platform activity.
Access administrative functionality.
2.7 Protected Routes

Frontend:

/user/*
/dealer/*
/admin/*

Backend:

/api/users/*
/api/dealers/*
/api/admin/*

Backend authorization is mandatory.

2.8 Phase 1 Deliverables
[ ] User registration
[ ] Login
[ ] Logout
[ ] Password hashing
[ ] Password reset if included
[ ] Authentication
[ ] Authorization
[ ] Role management
[ ] Protected routes
[ ] Backend authorization
[ ] Authentication tests
3. Phase 2 — Dashboard and Application Layout
Objective

Create the overall application interface and role-specific dashboards.

3.1 Global Application Layout

Create:

Navbar
Sidebar where required
Footer
Main content area
Responsive layout
Loading states
Error states

The UI must be responsive for:

Desktop
Tablet
Mobile
3.2 User Dashboard

The user dashboard should provide an overview of the user's activities.

Potential cards:

Recommended Properties
Saved Properties
Recent Searches
Active Chats
Design Projects
Cost Estimates
3.3 Dealer Dashboard

The dealer dashboard should provide:

Total Properties
Active Listings
Customer Inquiries
Active Conversations
Recent Activity
3.4 Admin Dashboard

The admin dashboard should provide high-level statistics such as:

Total Users
Total Dealers
Total Properties
Active Listings
Total Conversations
System Activity

Only authorized administrators may access this dashboard.

3.5 Navigation

Navigation must change according to the authenticated role.

Example:

Visitor
 ├── Home
 ├── Properties
 ├── AI Chatbot
 └── Login

User
 ├── Dashboard
 ├── Properties
 ├── Recommendations
 ├── 2D Design
 ├── 3D Design
 ├── Interior Design
 ├── Cost Estimation
 ├── AI Chatbot
 └── Dealer Chat

Dealer
 ├── Dashboard
 ├── My Properties
 ├── Add Property
 ├── Customers
 └── Chat

Admin
 ├── Dashboard
 ├── Users
 ├── Dealers
 ├── Properties
 ├── Reports
 └── System Management
3.6 Overview Cards and Statistics

Implement reusable statistic cards.

Examples:

Properties
Users
Dealers
Recommendations
Chats
Design Projects

Statistics must be retrieved from backend APIs rather than hardcoded.

3.7 Basic Data Visualization

Where useful, provide basic visualizations.

Admin examples:

User growth
Property listings
Property types
Activity statistics

Dealer examples:

Property listings
Inquiry statistics
Customer activity

Visualization must be based on actual application data.

3.8 Phase 2 Deliverables
[ ] Global layout
[ ] Responsive navigation
[ ] User dashboard
[ ] Dealer dashboard
[ ] Admin dashboard
[ ] Overview cards
[ ] Statistics APIs
[ ] Basic charts
[ ] Protected dashboard routes
4. Phase 3 — CRUD Operations
Objective

Implement the core data management functionality of the platform.

CRUD means:

Create
Read
Update
Delete
4.1 Main Entities

The primary entities include:

User
Dealer
Property
Property Image
Chat
Message
Design Project
Cost Estimate
Recommendation

Administrative operations may also be performed on:

Users
Dealers
Properties
Reports
4.2 User CRUD

Users should be able to manage their own profile.

Potential operations:

Read Profile
Update Profile

Administrators may manage users according to their permissions.

4.3 Dealer CRUD

Dealers should be able to:

Create Profile
Read Profile
Update Profile

Admins may manage dealer accounts.

4.4 Property CRUD

This is one of the primary CRUD systems.

Dealers should be able to:

Create

Create a property listing containing:

Title
Description
Property Type
Price
Location
Area
Bedrooms
Bathrooms
Features
Images
Dealer
Read

Users and authorized users can view:

Property list
Property details
Dealer information
Property images
Update

Dealers can update their own property listings.

Delete

Dealers can delete their own listings.

Admins can manage property records according to administrative permissions.

4.5 Property List View

Create a property listing interface.

Each property card may display:

Image
Title
Location
Price
Area
Bedrooms
Bathrooms
Property Type
4.6 Property Details View

Create a dedicated property details page.

It should contain:

Property Images
Property Information
Description
Location
Price
Specifications
Dealer Information
Contact/Chat Option
Recommendation/Related Properties
4.7 Search

Implement property search.

Potential search parameters:

Location
Property Type
Minimum Price
Maximum Price
Minimum Area
Maximum Area
Bedrooms
Bathrooms

Search should be processed through backend APIs.

4.8 Filter

Users should be able to filter properties based on their requirements.

Example:

Location = Islamabad
Property Type = House
Budget = 10,000,000
Bedrooms >= 3
4.9 Sort

Support useful sorting options:

Price: Low → High
Price: High → Low
Newest
Oldest
Area: Small → Large
Area: Large → Small
4.10 Pagination

Property lists must use pagination when the dataset becomes large.

Example:

Page 1
Page 2
Page 3
...

Do not load the entire database into the frontend.

4.11 Form Validation

All important forms require:

Frontend validation

For user experience.

Backend validation

For security and data integrity.

Forms include:

Signup
Login
Property Creation
Property Update
Dealer Profile
Cost Estimation
Design Settings
Chat
4.12 Chat CRUD

Implement the underlying data operations for:

Create Conversation
Read Conversation
Send Message
Read Messages

Delete/edit behavior should follow the final chat requirements.

4.13 Phase 3 Deliverables
[ ] User profile CRUD
[ ] Dealer CRUD
[ ] Property CRUD
[ ] Property images
[ ] Property list
[ ] Property details
[ ] Search
[ ] Filtering
[ ] Sorting
[ ] Pagination
[ ] Form validation
[ ] Chat/message operations
[ ] Admin CRUD operations
5. Phase 4 — Additional Features and AI Modules
Objective

Implement the intelligent and specialized functionality that differentiates this project from a normal real-estate website.

This is the most feature-heavy phase.

5.1 Centralized AI Chatbot

The platform will contain a centralized AI chatbot.

Architecture:

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
Response
 ↓
FastAPI
 ↓
React

The chatbot should provide assistance related to:

Real Estate
Properties
Construction
Design
Cost Estimation
Property Recommendations
Platform Help
5.2 AI Intent Detection

The centralized chatbot should identify the user's intent where required.

Example:

User:
"Find me a house in Islamabad under 2 crore."

        ↓

Intent:
PROPERTY_SEARCH

        ↓

Property Search Module

        ↓

Results

Another example:

User:
"How much will it cost to construct a 5 marla house?"

        ↓

Intent:
COST_ESTIMATION

        ↓

Cost Estimation Module
5.3 AI Request Routing

The chatbot may route supported requests to application modules.

Possible routes:

PROPERTY_SEARCH
PROPERTY_RECOMMENDATION
COST_ESTIMATION
DESIGN_2D
DESIGN_3D
INTERIOR_DESIGN
GENERAL_REAL_ESTATE
PLATFORM_HELP

Routing must not bypass backend authorization.

5.4 AI Model Integration

Ollama will be integrated through the backend.

Requirements:

[ ] Ollama service
[ ] Configurable model
[ ] AI service
[ ] Prompt management
[ ] Request validation
[ ] Response handling
[ ] Timeout handling
[ ] AI error handling
[ ] Fallback response
5.5 Property Recommendation System

The recommendation system should recommend properties based on user requirements.

Possible inputs:

Budget
Location
Property Type
Area
Bedrooms
Bathrooms
Preferences

Initial implementation may use:

Filtering
+
Scoring
+
Ranking

Example:

User Requirements
       ↓
Property Dataset
       ↓
Filtering
       ↓
Matching Score
       ↓
Ranking
       ↓
Recommended Properties

A machine-learning recommendation model can be introduced if required by the final project scope.

5.6 2D Design Module

Implement the 2D architectural/floor-plan design module.

Potential functionality:

Create Project
Create Floor
Add Room
Resize Room
Add Door
Add Window
Set Dimensions
Move Elements
Delete Elements
Save Design
Load Design

Example:

User
 ↓
2D Design Interface
 ↓
Create/Edit Floor Plan
 ↓
Save
 ↓
Backend
 ↓
Database

The 2D design system should be modular and independent from the core property-management system.

5.7 3D Design Module

Implement a 3D visualization environment.

Potential functionality:

Create 3D Scene
Add Rooms
Add Walls
Add Doors
Add Windows
Add Furniture
Modify Dimensions
Camera Navigation
Save Project
Load Project

The 3D engine must remain separated from the backend business logic.

5.8 Interior Design Module

Implement the interior design functionality.

Potential features:

Room Selection
Furniture Placement
Furniture Removal
Color Selection
Material Selection
Interior Styles
Layout Adjustment
Save Design
Load Design

Possible future AI integration:

User Requirements
       ↓
AI
       ↓
Interior Design Suggestion
       ↓
Design Interface

AI-generated suggestions must remain advisory.

5.9 Construction Cost Estimation

Implement a deterministic cost-estimation engine.

Possible inputs:

Location
Covered Area
Number of Floors
Construction Quality
Material Quality
Additional Features

Example:

Covered Area
      ×
Construction Rate
      +
Additional Costs
      =
Estimated Construction Cost

The calculation engine should be separate from the AI chatbot.

The chatbot may explain the result, but the actual numerical calculation should be performed by deterministic application logic.

The result must be clearly labeled:

Estimated Cost

and not:

Guaranteed Cost

5.10 User–Dealer Chat

Implement communication between authenticated users and dealers.

Requirements:

[ ] Create conversation
[ ] Send message
[ ] Receive message
[ ] Message history
[ ] Conversation list
[ ] Property context
[ ] Access control
[ ] Error handling

Real-time communication can use WebSockets if required.

A REST-based implementation may be used for the initial version if real-time communication is not required.

5.11 File Upload

Implement file upload where required.

Primary use cases:

Property Images
Design Assets
User/Dealer Profile Images

Rules:

Validate file type
Validate file size
Generate safe filenames
Prevent executable uploads
Handle upload failures
5.12 File Download

Where applicable, users should be able to download:

Saved Designs
Floor Plans
Cost Estimates
Reports

Access must be authorized.

A user must not be able to download another user's private files by changing an ID in the URL.

5.13 Notifications and Alerts

Implement notifications for important events.

Potential notifications:

New Dealer Message
Property Listing Updated
Recommendation Available
Design Saved
Cost Estimate Generated
Admin Alert
System Error

Notification types may include:

Success
Information
Warning
Error
5.14 Settings and Preferences

Users should have settings where appropriate.

Potential settings:

Profile Information
Notification Preferences
AI Preferences
Display Preferences
Property Preferences

Dealers may have:

Dealer Profile
Listing Preferences
Notification Preferences

Admins may have appropriate system settings.

5.15 Business Logic and Rules

Implement application-specific business rules.

Examples:

A dealer can only modify their own properties.

A normal user cannot access admin endpoints.

A user can only access authorized conversations.

An AI response cannot grant permissions.

A deleted property should not remain visible in active listings.

A recommendation must refer to an actual available property.

A cost estimate must use the approved calculation logic.
5.16 Phase 4 Deliverables
[ ] Centralized AI chatbot
[ ] Ollama integration
[ ] AI intent detection
[ ] AI request routing
[ ] Property recommendation
[ ] 2D design
[ ] 3D design
[ ] Interior design
[ ] Construction cost estimation
[ ] User-dealer chat
[ ] File upload
[ ] File download
[ ] Notifications
[ ] Settings/preferences
[ ] Business rules
6. Phase 5 — Testing and Quality Assurance
Objective

Verify that the complete system works correctly, securely, and reliably.

6.1 Unit Testing

Test individual functions, services, and components.

Backend:

Authentication
Property Service
Recommendation Service
Cost Calculation
AI Service
Authorization

Frontend:

Forms
Property Cards
Chat Components
Dashboard Components
Design Components
6.2 Integration Testing

Test communication between components.

Examples:

Frontend → FastAPI
FastAPI → PostgreSQL
FastAPI → Ollama
Authentication → Protected APIs
Property → Recommendation
User → Dealer Chat
6.3 Authentication Testing

Test:

Signup
Login
Logout
Invalid credentials
Password reset
Protected routes
Role authorization
Admin authorization
6.4 CRUD Testing

Test:

Create
Read
Update
Delete
Search
Filter
Sort
Pagination

for relevant entities.

6.5 AI Testing

Test:

Normal questions
Real-estate questions
Property search requests
Recommendation requests
Cost estimation requests
Design requests
Unsupported requests
Invalid requests
Ollama unavailable
AI timeout
AI malformed response
6.6 AI Safety Testing

Verify that AI cannot:

Bypass authentication
Bypass authorization
Expose secrets
Expose private user information
Perform unauthorized admin actions
Invent database properties
Execute arbitrary commands
6.7 Design Module Testing

Test:

2D
Create room
Resize room
Add door
Add window
Save
Load
Delete
3D
Create scene
Add object
Move object
Remove object
Camera navigation
Save
Load
Interior
Add furniture
Remove furniture
Change colors
Change materials
Save
Load
6.8 Construction Cost Testing

Use known test cases.

Example:

Input:
Area = X
Rate = Y

Expected:
Cost = X × Y

Test:

Normal values
Zero values
Negative values
Missing values
Very large values
Invalid input
6.9 User–Dealer Chat Testing

Verify:

User can message dealer.
Dealer can respond.
Unauthorized users cannot access conversation.
Messages persist correctly.
Invalid conversation IDs are rejected.
6.10 Security Testing

Check:

Authentication
Authorization
Input validation
Password storage
API protection
File uploads
Access control
Secret management
SQL injection protection
XSS protection
6.11 Performance Testing

Measure:

API response time
Database query performance
Property search performance
AI response time
Dashboard loading
File upload performance
3D rendering performance

The system should remain usable under expected project load.

6.12 Bug Fixing

All discovered bugs should be:

Identified
 ↓
Reproduced
 ↓
Documented
 ↓
Fixed
 ↓
Tested
 ↓
Regression Tested
6.13 Phase 5 Deliverables
[ ] Unit tests
[ ] Integration tests
[ ] Authentication tests
[ ] Authorization tests
[ ] CRUD tests
[ ] AI tests
[ ] Design tests
[ ] Cost estimation tests
[ ] Chat tests
[ ] Security testing
[ ] Performance testing
[ ] Bug fixing
[ ] Regression testing
7. Phase 6 — Deployment and Maintenance
Objective

Deploy the complete application and establish a process for monitoring, feedback, maintenance, and future improvements.

7.1 Production Preparation

Before deployment:

[ ] Environment variables configured
[ ] Production database configured
[ ] Secrets secured
[ ] Debug mode disabled
[ ] CORS configured
[ ] Authentication verified
[ ] Authorization verified
[ ] Database migrations completed
[ ] Docker images tested
[ ] Frontend production build tested
[ ] Backend production startup tested
7.2 Docker Deployment

The application should be containerized.

Potential architecture:

                 Docker Environment
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
   Frontend         Backend        PostgreSQL
                       │
                       ▼
                    Ollama

Docker Compose may be used for multi-container deployment.

7.3 Staging Deployment

Before production:

Development
     ↓
Staging
     ↓
Testing
     ↓
Bug Fixes
     ↓
Production

The staging environment should be used to verify:

Authentication
APIs
Database
AI
Chat
Design modules
File handling
Admin functionality
7.4 User Feedback

Collect feedback about:

Usability
Performance
AI responses
Property search
Recommendations
Design modules
Cost estimation
Chat
Dashboard
Mobile responsiveness

Feedback should be categorized into:

Bug
Improvement
Feature Request
Usability Issue
Performance Issue
Security Issue
7.5 Monitoring

Monitor:

Application availability
API errors
Database errors
AI service availability
Response times
Authentication failures
Storage usage
Server resources

Do not collect unnecessary personal information in monitoring systems.

7.6 Bug Fixes

After deployment:

Bug Report
 ↓
Reproduce
 ↓
Determine Root Cause
 ↓
Fix
 ↓
Test
 ↓
Deploy
 ↓
Monitor

Critical security problems receive the highest priority.

7.7 Feature Enhancements

Future features may include:

Advanced ML recommendation
Property price prediction
AI-generated interior designs
Advanced 3D visualization
Real-time WebSocket chat
Maps integration
Property comparison
Wishlist
Notifications
Mobile application
Advanced analytics

New features must follow:

Requirement
 ↓
Impact Analysis
 ↓
Architecture Review
 ↓
Implementation
 ↓
Testing
 ↓
Documentation
 ↓
Deployment
7.8 Maintenance

Maintenance includes:

Dependency updates
Security patches
Database maintenance
Performance optimization
Bug fixes
AI model updates
Documentation updates
Backup management

Dependencies must not be updated blindly in production.

7.9 Backup and Recovery

The production database should have an appropriate backup strategy.

Backups should be:

Automated where possible.
Stored securely.
Tested periodically.
Protected from unauthorized access.

Recovery procedures should be documented.

7.10 Phase 6 Deliverables
[ ] Production configuration
[ ] Docker deployment
[ ] Staging deployment
[ ] Staging testing
[ ] Production deployment
[ ] Monitoring
[ ] User feedback
[ ] Bug fixing
[ ] Performance improvements
[ ] Security maintenance
[ ] Documentation updates
[ ] Future feature planning
8. Overall Development Roadmap

The complete project roadmap is:

                         PROJECT
                            │
                            ▼
                 ┌────────────────────┐
                 │     PHASE 1        │
                 │ Authentication     │
                 │ Authorization      │
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │     PHASE 2        │
                 │ Dashboards         │
                 │ Navigation        │
                 │ Statistics         │
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │     PHASE 3        │
                 │ CRUD               │
                 │ Properties         │
                 │ Users              │
                 │ Dealers            │
                 │ Search/Filter      │
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │     PHASE 4        │
                 │ AI & Advanced      │
                 │ Features           │
                 └─────────┬──────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
      AI Chatbot       Recommendation    Design
          │                                 │
          │                    ┌────────────┼────────────┐
          │                    │            │            │
          ▼                    ▼            ▼            ▼
       Ollama                 2D           3D       Interior
                               Design      Design     Design
          │
          ▼
     AI Routing
          │
          ▼
    Cost Estimation
          │
          ▼
      Dealer Chat
          │
          ▼
      Notifications
          │
          ▼
    File Management
                           │
                           ▼
                 ┌────────────────────┐
                 │     PHASE 5        │
                 │ Testing & QA       │
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │     PHASE 6        │
                 │ Deployment         │
                 │ Monitoring         │
                 │ Maintenance        │
                 └────────────────────┘
9. Phase Completion Rule

A phase is considered complete only when:

[ ] Functionality implemented
[ ] Frontend completed
[ ] Backend completed
[ ] Database integration completed where required
[ ] Authentication/authorization verified
[ ] Error handling implemented
[ ] Tests completed
[ ] Bugs fixed
[ ] Documentation updated

A feature should not be considered complete merely because its UI exists.

10. AI Coding Agent Development Rule

When Claude Code or another AI coding agent works on this project, it must follow the phases.

The AI should:

Identify the current phase.
Read the relevant documentation.
Inspect existing implementation.
Implement only the required functionality.
Avoid prematurely implementing future phases.
Run tests.
Fix errors.
Update documentation.
Report what was completed.

For example:

Current Phase:
Phase 1 — Authentication

Allowed:
✓ Signup
✓ Login
✓ Logout
✓ Password reset
✓ RBAC
✓ Protected routes

Not yet required:
✗ 3D design
✗ Interior design
✗ Advanced recommendation model
✗ Production deployment

This prevents the AI coding agent from jumping between unrelated modules.

11. Definition of Done

A feature is considered complete when:

Requirement satisfied
        ↓
Implementation complete
        ↓
Frontend integrated
        ↓
Backend integrated
        ↓
Database integrated where required
        ↓
Validation implemented
        ↓
Error handling implemented
        ↓
Authorization verified
        ↓
Tests pass
        ↓
No known critical bugs
        ↓
Documentation updated
12. Final Project Phase Principle

The project should be developed incrementally.

The core principle is:

Build the foundation first, establish secure authentication and architecture, implement core real-estate functionality, then add AI and advanced design capabilities, followed by rigorous testing and deployment.

The AI components — centralized chatbot, intent detection, request routing, property recommendation, 2D design assistance, 3D design, and interior design — must remain integrated with the overall architecture rather than becoming isolated features.

The final system must function as one unified AI-powered real-estate platform.


### Recommended documentation structure now

Your project documentation is becoming much stronger:

```text
project/
│
├── CLAUDE.md
│
└── docs/
    │
    ├── PRD.md
    ├── architecture.md
    ├── rules.md
    ├── phase.doc.md       ← NEW
    │
    ├── requirements.md
    ├── database.md
    ├── api.md
    ├── authentication.md
    ├── authorization.md
    ├── ai.md
    ├── chat.md
    ├── admin.md
    ├── property.md
    ├── recommendation.md
    ├── design.md
    ├── cost-estimation.md
    ├── testing.md
    └── deployment.md