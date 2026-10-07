# AI-Powered Real Estate Platform
## UI/UX Design System and Guidelines

**Document:** `design.md`
**Version:** 1.0
**Status:** Active
**Frontend:** React + Tailwind CSS
**Design Approach:** Mobile-First, Responsive, Accessible, Component-Based

---

# 1. Purpose

This document defines the visual design system, UI/UX principles, typography, color system, responsive behavior, accessibility requirements, component standards, and user-interface preferences for the AI-powered real-estate platform.

The purpose is to ensure that every module provides a consistent experience.

The design system applies to:

- Public website
- User dashboard
- Dealer dashboard
- Admin dashboard
- Property listings
- Property details
- Centralized AI chatbot
- Property recommendation
- 2D design
- 3D design
- Interior design
- Construction cost estimation
- User-dealer chat
- Authentication
- Notifications
- Settings
- Forms
- Reports and analytics

---

# 2. UI/UX Design

## 2.1 Core Design Principles

The platform should follow these principles:

```text
Simple
Consistent
Responsive
Accessible
Intuitive
Fast
Reusable
Professional

The interface should prioritize usability over unnecessary visual complexity.

2.2 Clean and Intuitive Interface

The interface should allow users to understand what they can do without requiring extensive instructions.

Rules
Use clear labels.
Use familiar UI patterns.
Keep navigation predictable.
Avoid unnecessary popups.
Avoid excessive animations.
Maintain sufficient whitespace.
Group related information together.
Use visual hierarchy to emphasize important information.
Use meaningful icons together with text where appropriate.
Avoid overcrowding pages.

Example:

Property Card
┌──────────────────────────────┐
│                              │
│        Property Image        │
│                              │
├──────────────────────────────┤
│ 5 Marla House                │
│ Islamabad                    │
│                              │
│ PKR 2.5 Crore                │
│ 3 Beds • 3 Baths             │
│                              │
│ [ View Details ]             │
└──────────────────────────────┘
2.3 Consistent User Experience

All modules must follow the same design language.

For example:

Authentication
      ↓
Dashboard
      ↓
Properties
      ↓
Design
      ↓
AI Chatbot

The user should feel that all modules belong to the same application.

Consistency must be maintained in:

Buttons
Cards
Forms
Inputs
Modals
Navigation
Tables
Alerts
Icons
Typography
Spacing
Colors
Loading states
Error states
2.4 Mobile-First Approach

The project should follow a mobile-first responsive design approach.

Design should begin with small screens and progressively adapt to larger screens.

Target:

Mobile
  ↓
Tablet
  ↓
Desktop
  ↓
Large Desktop

The interface must not be designed only for desktop and then compressed for mobile.

2.5 Responsive Breakpoints

Use Tailwind CSS responsive breakpoints.

General guideline:

Mobile:
< 640px

Tablet:
640px – 1023px

Desktop:
1024px – 1279px

Large Desktop:
1280px+

The exact breakpoint should be selected based on component behavior rather than device names alone.

2.6 Mobile Navigation

On mobile devices:

Use a compact navigation system.
Use a hamburger/drawer menu where appropriate.
Keep primary actions easily accessible.
Avoid excessively wide tables.
Convert complex desktop layouts into stacked layouts.
Make buttons touch-friendly.
2.7 Accessibility

Accessibility is a core requirement.

The application should aim to follow WCAG principles.

Requirements
Provide meaningful labels for form inputs.
Use semantic HTML.
Provide accessible button names.
Maintain sufficient color contrast.
Do not rely only on color to communicate information.
Support keyboard navigation where applicable.
Provide visible focus states.
Provide alternative text for meaningful images.
Ensure interactive elements are usable on touch devices.
Avoid excessively small text.
Use accessible modal/dialog behavior.

Example:

Do not:

🔴

as the only indication of an error.

Prefer:

⚠ Error: Please enter a valid email address.
2.8 Navigation

Navigation should be predictable and role-aware.

Visitor
Home
Properties
AI Assistant
Login
User
Dashboard
Properties
Recommendations
2D Design
3D Design
Interior Design
Cost Estimation
AI Assistant
Messages
Settings
Dealer
Dashboard
My Properties
Add Property
Messages
Profile
Settings
Admin
Dashboard
Users
Dealers
Properties
Reports
System Management
Settings

Users must not see navigation options that they are not authorized to use.

However, hiding a navigation item is not an authorization mechanism.

2.9 Component Reuse

The UI must be built using reusable React components.

Examples:

Button
Input
Select
Modal
Card
PropertyCard
PropertyGrid
Navbar
Sidebar
Dropdown
Badge
Alert
Toast
LoadingSpinner
Pagination
SearchBar
FilterPanel
ChatMessage
ChatInput
StatCard
Table

Avoid creating multiple versions of the same component without a strong reason.

2.10 Component Consistency

A component should behave consistently throughout the application.

For example:

Primary Button

should have the same:

Color
Border radius
Typography
Hover behavior
Focus behavior
Disabled behavior

across all modules.

2.11 UI States

Every important component should account for:

Default
Hover
Focus
Active
Disabled
Loading
Success
Error
Empty

Example:

Property List

Loading:
"Loading properties..."

Empty:
"No properties found."

Error:
"Unable to load properties. Please try again."

Success:
"Property added successfully."
2.12 Loading States

Do not leave users staring at a blank screen while data loads.

Use:

Skeleton loaders
Spinners
Progress indicators

where appropriate.

For large property lists, skeleton cards are preferred over a full-page spinner when practical.

2.13 Empty States

Empty states should explain what happened and what the user can do next.

Bad:

No data.

Better:

No saved properties yet.

Browse properties and save the ones
you are interested in.

Provide a relevant action where appropriate.

2.14 Error States

Errors should be:

Clear
Short
Human-readable
Actionable

Example:

Unable to load recommendations.

Please try again.

Do not expose technical errors such as:

500 Internal Server Error
SQLAlchemy Exception...

to normal users.

2.15 Forms

Forms must have:

Clear labels
Appropriate input types
Validation
Helpful error messages
Required-field indicators where applicable
Submit/loading state
Success feedback

Example:

Property Price
[________________]

Please enter a valid price.
2.16 Property Listing UI

Property cards should provide essential information without overwhelming the user.

Recommended information:

Property Image
Property Title
Location
Price
Property Type
Area
Bedrooms
Bathrooms
Favorite/Save Action
View Details

Additional information can be displayed on the details page.

2.17 Property Details UI

The property details page should prioritize:

Images
Price
Location
Main Specifications
Description
Features
Dealer Information
Contact Dealer
Similar Properties

Important actions should be visually distinguishable.

2.18 AI Chatbot UI

The centralized chatbot should have a familiar conversational interface.

Structure:

┌──────────────────────────────────┐
│ AI Real Estate Assistant         │
├──────────────────────────────────┤
│                                  │
│ AI: How can I help you?          │
│                                  │
│ User: Find a house in Islamabad  │
│                                  │
│ AI: Here are some properties...  │
│                                  │
├──────────────────────────────────┤
│ Type your message...       [➤]   │
└──────────────────────────────────┘

The chatbot should support:

Message history
Loading indicator
Error state
Retry action
Clear conversation where applicable
Contextual actions
Links to relevant platform modules
2.19 AI Response Presentation

AI responses should be easy to read.

Use:

Paragraphs
Lists
Headings
Tables where appropriate
Property cards for property results
Action buttons for relevant tasks

Avoid displaying raw JSON or technical model output to normal users.

2.20 Design Module UI

The 2D, 3D, and interior design interfaces may use a specialized workspace layout.

Example:

┌─────────────────────────────────────────┐
│ Toolbar                                 │
├─────────────┬───────────────────────────┤
│             │                           │
│ Tools       │       Design Canvas       │
│             │                           │
│ Rooms       │                           │
│ Doors       │                           │
│ Windows     │                           │
│ Furniture   │                           │
│             │                           │
├─────────────┴───────────────────────────┤
│ Properties / Dimensions / Controls      │
└─────────────────────────────────────────┘

The design workspace may intentionally differ from the standard dashboard layout because it is a specialized application environment.

However, colors, typography, controls, and interaction patterns should remain consistent with the overall design system.

2.21 Dashboard UI

Dashboards should prioritize information hierarchy.

Recommended structure:

Sidebar
   +
Header
   +
Overview Cards
   +
Charts / Statistics
   +
Recent Activity
   +
Relevant Actions

Avoid filling the dashboard with unnecessary charts.

Every visualization should communicate useful information.

2.22 Admin UI

The admin interface should prioritize:

Information density
Data tables
Search
Filtering
Sorting
Pagination
Clear actions
Confirmation dialogs
Audit-related information where applicable

Administrative actions that can cause destructive changes should require confirmation.

3. Color and Theme
3.1 Design Direction

The visual style should communicate:

Professional
Modern
Trustworthy
Clean
Technology-focused
Real-estate oriented

The platform should avoid overly bright or distracting colors.

3.2 Primary Color
Primary

Use:

Primary: #2563EB

Purpose:

Primary buttons
Links
Active navigation
Important actions
Selected states
Interactive elements

Tailwind equivalent:

blue-600
3.3 Secondary Color
Secondary

Use:

Secondary: #0F766E

Purpose:

Secondary actions
Supporting UI
Selected filters
Secondary highlights

Tailwind equivalent:

teal-700
3.4 Accent Color
Accent

Use:

Accent: #F59E0B

Purpose:

Highlights
Recommendations
Important attention points
Featured properties
Rating/favorite-related UI where appropriate

Tailwind equivalent:

amber-500

Accent color should not be overused.

3.5 Background Colors
Light Theme

Main background:

#F8FAFC

Tailwind:

slate-50
Dark Theme

Main background:

#0F172A

Tailwind:

slate-900
3.6 Surface Colors

Surfaces include:

Cards
Panels
Modals
Sidebars
Input containers
Light
Surface:
#FFFFFF
Dark
Surface:
#1E293B

Tailwind:

slate-800
3.7 Text Colors
Light Theme

Primary text:

#0F172A

Secondary text:

#475569

Muted text:

#64748B
Dark Theme

Primary text:

#F8FAFC

Secondary text:

#CBD5E1

Muted text:

#94A3B8
3.8 Border Colors

Light:

#E2E8F0

Dark:

#334155

Borders should be subtle and should not visually dominate the interface.

3.9 Status Colors
Success
#16A34A

Tailwind:

green-600

Use for:

Successful operations
Confirmations
Completed processes
Available status
Warning
#D97706

Tailwind:

amber-600

Use for:

Warnings
Uncertain information
Pending operations
Estimated values
Error
#DC2626

Tailwind:

red-600

Use for:

Validation errors
Failed operations
Access denied
System errors
Information
#0284C7

Tailwind:

sky-600

Use for:

Informational messages
Helpful tips
Non-critical notifications
3.10 Color Usage Rules

Do not use colors randomly.

Use:

Primary
→ Main interactive actions

Secondary
→ Supporting actions

Accent
→ Highlights

Success
→ Successful state

Warning
→ Warning state

Error
→ Error state

Information
→ Informational state

Do not use red simply because it looks attractive.

Red should primarily communicate danger, deletion, or errors.

3.11 Light Theme

The light theme should use:

Background → Slate-50
Surface → White
Primary Text → Slate-900
Secondary Text → Slate-600
Border → Slate-200

The interface should remain visually clean and avoid excessive shadows.

3.12 Dark Theme

The dark theme should use:

Background → Slate-900
Surface → Slate-800
Primary Text → Slate-50
Secondary Text → Slate-300
Border → Slate-700

Avoid pure black backgrounds such as:

#000000

for the primary application background unless there is a specific design requirement.

3.13 Theme Switching

Users should be able to select:

Light
Dark
System

Recommended default:

System

The selected theme should persist across sessions.

4. Fonts and Typography
4.1 Primary Font Family

Use:

Inter

Fallback:

system-ui
sans-serif

CSS/Tailwind concept:

font-family: Inter, system-ui, sans-serif;

Inter should be used consistently across:

Website
Dashboard
Forms
Chat
Property pages
Admin interface
4.2 Typography Hierarchy

Typography should establish a clear visual hierarchy.

Recommended scale:

Element	Size	Weight	Line Height
H1	36px	700	1.2
H2	30px	700	1.25
H3	24px	600	1.3
H4	20px	600	1.35
H5	18px	600	1.4
H6	16px	600	1.4
Body	16px	400	1.5
Small	14px	400	1.5
Caption	12px	400	1.4
4.3 H1

Use H1 for the primary page heading.

Example:

Find Your Perfect Property

Recommended:

36px
700
1.2 line-height

On small screens, H1 may scale down responsively.

4.4 H2

Use H2 for major sections.

Example:

Recommended Properties

Recommended:

30px
700
1.25 line-height
4.5 H3

Use H3 for subsections.

Example:

Property Details

Recommended:

24px
600
1.3 line-height
4.6 H4–H6

Use lower-level headings to maintain semantic hierarchy.

Do not choose heading levels only because of visual size.

HTML semantics should reflect document structure.

4.7 Body Text

Default body:

16px
400
1.5 line-height

Body text should be comfortable to read on both desktop and mobile.

4.8 Small Text

Use:

14px
400
1.5 line-height

for:

Secondary information
Supporting text
Form hints
Metadata
4.9 Caption Text

Use:

12px
400
1.4 line-height

for:

Timestamps
Small metadata
Non-critical supporting information

Do not use caption-sized text for important information.

4.10 Font Weight

Approved weights:

400 → Regular
500 → Medium
600 → Semibold
700 → Bold

Guideline:

Body       → 400
Labels     → 500
Subheading → 600
Heading    → 700

Avoid using very heavy font weights everywhere.

4.11 Typography Responsiveness

Typography should adapt to screen size.

Example:

Desktop:
H1 = 36px

Mobile:
H1 = 30px

The exact responsive scale can be adjusted based on layout requirements.

5. Spacing System

Use a consistent spacing scale.

Preferred Tailwind spacing values:

4px
8px
12px
16px
20px
24px
32px
40px
48px
64px

Avoid arbitrary spacing values unless necessary.

5.1 Component Spacing

Recommended:

Input gap:
8–12px

Form field gap:
16–24px

Card padding:
16–24px

Section spacing:
32–64px
6. Border Radius

Use consistent rounded corners.

Recommended:

Small:
6px

Medium:
8px

Large:
12px

Extra Large:
16px

General guideline:

Inputs:
8px

Buttons:
8px

Cards:
12px

Large panels:
16px

Avoid excessive rounding that makes the interface look inconsistent.

7. Shadows

Shadows should be subtle.

Use shadows primarily for:

Cards requiring elevation
Dropdowns
Modals
Floating elements

Avoid heavy shadows throughout the entire application.

Prefer borders and subtle elevation for most cards.

8. Icons

Use one consistent icon library throughout the interface.

Preferred:

Lucide Icons

Rules:

Use icons consistently.
Do not mix many unrelated icon styles.
Provide accessible labels for icon-only buttons.
Use familiar icons.
Do not use icons as the only indicator of critical information.
9. Buttons
9.1 Primary Button

Used for the main action.

Examples:

Login
Create Property
Save Design
Send Message
Get Estimate
9.2 Secondary Button

Used for supporting actions.

Examples:

Cancel
Back
View Details
9.3 Destructive Button

Used for irreversible or destructive actions.

Examples:

Delete Property
Delete Conversation
Remove Design

Destructive actions should normally require confirmation.

10. Cards

Cards should be used for:

Properties
Statistics
Recommendations
Dashboard widgets
Notifications

Cards should have consistent:

Padding
Border
Radius
Typography
Spacing
Hover behavior
11. Tables

Tables are primarily used in administrative interfaces.

Requirements:

Clear column headings
Horizontal scrolling on small screens
Pagination where required
Search/filter support where appropriate
Consistent row spacing
Clear action controls

On mobile, tables may transform into cards if horizontal scrolling would create poor usability.

12. Modals and Dialogs

Use modals for:

Confirmation
Short forms
Important warnings
Focused actions

Do not use modals for entire pages.

Destructive operations should use confirmation dialogs.

Example:

Delete Property?

This action cannot be undone.

[Cancel] [Delete]
13. Notifications and Toasts

Notifications should provide immediate feedback.

Examples:

✓ Property created successfully.

✓ Design saved successfully.

⚠ AI service is temporarily unavailable.

✕ Unable to save property.

Notifications should not remain on screen unnecessarily.

14. User Preferences and UI Memory

The application should remember appropriate user interface preferences.

14.1 Theme Preference

Remember:

Light
Dark
System

The preference should persist after:

Logout
Browser restart
Page refresh

unless the user explicitly resets it.

14.2 Theme Storage

For non-sensitive UI preferences, the frontend may use:

localStorage

Example conceptual key:

theme

Do not store sensitive authentication information in ordinary UI preference storage.

14.3 Other UI Preferences

The system may remember:

Sidebar collapsed/expanded
Preferred property view
Grid/List view
Selected filters where appropriate
Dashboard layout preferences if implemented
Language preference if supported
Notification display preferences

Only persist preferences that provide meaningful user benefit.

14.4 Property View Preference

Users may select:

Grid View
List View

The application may remember the selection.

Example:

propertyView = grid
14.5 Sidebar Preference

On desktop, remember:

Expanded
Collapsed

On mobile, navigation should normally remain controlled by the mobile navigation system.

14.6 Filter Preference

The system may remember frequently used filters where appropriate.

However, filters should not unexpectedly persist forever.

Provide a clear way to reset filters.

14.7 User Preference Security

Never store sensitive information as UI preferences.

Do not store:

Passwords
API Keys
Authentication Secrets
Private Tokens
Sensitive Personal Data

in localStorage or other client-side preference storage.

15. Animation and Motion

Animations should be subtle and purposeful.

Use animation for:

Page transitions
Loading states
Dropdowns
Modals
Hover states
Feedback

Avoid:

Excessive animation
Long transitions
Distracting effects
Animation that blocks user interaction

Preferred transition duration:

150ms – 300ms

where appropriate.

15.1 Reduced Motion

Respect user accessibility preferences such as reduced motion.

Animations should be reduced or disabled when the user has enabled reduced-motion settings.

16. Responsive Design Rules

Every page must be tested at:

Mobile
Tablet
Desktop
Large Desktop

Important areas:

Navigation
Property cards
Forms
Dashboards
Tables
Chat
Design workspace
Modals
Images
Charts

No page should require horizontal scrolling unless the content naturally requires it, such as certain specialized design workspaces or data tables.

17. AI-Specific UI Design

AI functionality must be visually distinguishable but should remain part of the overall application design system.

17.1 AI Assistant Identity

The AI assistant may use:

AI icon
Assistant label
Subtle accent styling

Avoid excessive futuristic visual effects.

The interface should remain professional.

17.2 AI Loading State

When the AI is processing:

AI is thinking...

or an equivalent loading indicator should be shown.

Do not make users think the application has frozen.

17.3 AI Uncertainty

When AI information may be uncertain, the UI should communicate that appropriately.

For example:

Estimated construction cost

rather than presenting it as a guaranteed quotation.

17.4 AI Error State

If the AI service fails:

AI assistant is temporarily unavailable.

Please try again later.

Provide a retry action where appropriate.

18. Design Module UI Rules

The specialized design modules may use denser interfaces than normal pages.

18.1 2D Design

Recommended interface:

Toolbar
+
Tools Panel
+
2D Canvas
+
Properties Panel

The canvas should have clear visual distinction from surrounding controls.

18.2 3D Design

Recommended interface:

Toolbar
+
Object Library
+
3D Viewport
+
Properties Panel
+
Camera Controls

Controls should not obstruct the main viewport unnecessarily.

18.3 Interior Design

Recommended interface:

Furniture Library
+
Room Canvas/Viewport
+
Material Controls
+
Color Controls
+
Properties
19. Real Estate Visual Guidelines

Property imagery is one of the most important visual elements of the platform.

Rules:

Use consistent image aspect ratios in cards.
Use object-fit behavior to prevent distortion.
Provide image placeholders when images are unavailable.
Use optimized image sizes.
Provide meaningful alt text.
Use image galleries for property details.
Avoid stretching images.
20. Accessibility and Color Independence

Never communicate important information using color alone.

Instead of:

Green = Available
Red = Unavailable

use:

✓ Available
✕ Unavailable

with appropriate colors as supporting information.

21. Design Consistency Rules

Before creating a new UI component, check whether an existing component can be reused.

Preferred:

Existing Button
      ↓
Reuse

instead of:

Create New Button

for every module.

22. UI Component Hierarchy

The frontend should generally follow:

Pages
  ↓
Layouts
  ↓
Feature Components
  ↓
Shared Components
  ↓
Primitive UI Components

Example:

PropertyDetailsPage
        ↓
PropertyGallery
PropertyInformation
DealerCard
RecommendationSection
        ↓
Card
Button
Badge
Image
23. Design Review Checklist

Before considering a UI feature complete:

[ ] Layout is responsive
[ ] Mobile layout works
[ ] Desktop layout works
[ ] Typography is consistent
[ ] Colors follow design system
[ ] Components are reusable
[ ] Buttons have proper states
[ ] Forms have validation states
[ ] Loading state exists
[ ] Empty state exists
[ ] Error state exists
[ ] Success feedback exists
[ ] Accessibility considered
[ ] Keyboard interaction considered
[ ] Images are optimized
[ ] Dark mode works
[ ] User preferences persist where appropriate
24. Final Design Principle

The platform should follow this principle:

Create a clean, professional, accessible, mobile-first interface where every module feels like part of the same product while allowing specialized modules such as 2D design, 3D design, interior design, AI chat, dashboards, and property management to use interfaces appropriate to their specific tasks.

The interface should prioritize:

Usability
   ↓
Consistency
   ↓
Accessibility
   ↓
Performance
   ↓
Visual Quality

The design system must support the application's functionality rather than becoming a visual layer disconnected from the product architecture.


### Your documentation set is now becoming well-defined

I would now keep the project documentation organized like this:

```text
project/
│
├── CLAUDE.md
│
├── docs/
│   ├── PRD.md
│   ├── architecture.md
│   ├── rules.md
│   ├── phase.doc.md
│   └── design.md          ← NEW
│
├── frontend/
├── backend/
├── database/
└── docker-compose.yml