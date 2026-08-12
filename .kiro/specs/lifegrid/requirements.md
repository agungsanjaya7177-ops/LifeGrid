# Requirements Document

## Introduction

LifeGrid is a privacy-conscious personal life management dashboard designed for university students and young adults. The application unifies five life management areas — productivity, personal finance, personal development, fitness, and personal security — into a single cohesive full-stack web application. The central question LifeGrid answers is: **"What should I focus on today?"**

The system is built with a React/TypeScript/Vite/Tailwind CSS frontend, a Python/FastAPI REST backend, and a PostgreSQL database. The architecture is monolithic full-stack with a clearly separated frontend and backend. All user data is private to the owning user. No AI, no external financial/health APIs, no microservices.

---

## Glossary

- **System**: The LifeGrid web application as a whole.
- **Frontend**: The React/TypeScript/Vite/Tailwind CSS client application.
- **Backend**: The Python/FastAPI REST API server.
- **Database**: The PostgreSQL relational database.
- **Auth_Service**: The component responsible for user registration, login, logout, and JWT management.
- **Task_Manager**: The component responsible for creating, editing, deleting, and querying tasks.
- **Finance_Manager**: The component responsible for recording transactions and managing budgets.
- **Development_Tracker**: The component responsible for managing learning goals and progress.
- **Fitness_Tracker**: The component responsible for recording and querying workout sessions.
- **Security_Center**: The component responsible for managing and displaying the personal security checklist.
- **Dashboard**: The unified overview component that aggregates data from all five life modules.
- **Life_Score_Engine**: The deterministic, rule-based component that computes the Life Score.
- **Authenticated_User**: A user who has successfully logged in and holds a valid JWT.
- **Owner**: The Authenticated_User who originally created a given data record.
- **JWT**: JSON Web Token used as the bearer token for authentication.
- **IDR**: Indonesian Rupiah, the currency used for all financial values in the system.
- **Task**: A discrete unit of work with a title, optional deadline, priority, category, and completion status.
- **Transaction**: A single record of income or expense with an amount (IDR), category, date, and type.
- **Monthly_Budget**: A user-defined upper limit on total expenditure for a given calendar month.
- **Learning_Goal**: A named personal development objective with a target date and a progress percentage.
- **Workout_Session**: A manually recorded fitness activity with type, duration, date, and optional notes.
- **Security_Checklist**: An ordered list of security hygiene items, each with a checked/unchecked status.
- **Life_Score**: A single integer between 0 and 100 computed deterministically from the five module states.
- **Empty_State**: A UI state shown when a module contains no data, including a descriptive message and a call-to-action.

---

## Requirements

### Requirement 1: User Registration

**User Story:** As a new visitor, I want to register an account with my email and password, so that I can access my private LifeGrid dashboard.

#### Acceptance Criteria

1. WHEN a visitor submits a registration form with a valid email address and a password between 8 and 128 characters containing at least one uppercase letter, one lowercase letter, and one digit, THE Auth_Service SHALL create a new user account and return a success response.
2. WHEN a visitor submits a registration form with an email address that already exists in the Database, THE Auth_Service SHALL return an error response indicating that the email address is already in use without revealing how the existing account was registered.
3. IF a visitor submits a registration form with a password shorter than 8 characters, longer than 128 characters, or missing a required character class (uppercase, lowercase, or digit), THEN THE Auth_Service SHALL return a validation error response indicating which constraint was violated before attempting to persist the record.
4. IF a visitor submits a registration form with a malformed email address, THEN THE Auth_Service SHALL return a validation error response before attempting to persist the record.
5. THE Auth_Service SHALL store all user passwords as hashed values using a cryptographic hashing algorithm; THE Auth_Service SHALL NOT store plaintext passwords in the Database.
6. WHEN a new user account is created, THE Auth_Service SHALL return a JWT with an expiry duration of at most 24 hours that the Frontend can use for subsequent authenticated requests.
7. IF a database error occurs during account creation, THEN THE Auth_Service SHALL return a 500 Internal Server Error response and SHALL NOT persist a partial user record.

### Requirement 2: User Login

**User Story:** As a registered user, I want to log in with my email and password, so that I can access my personal data securely.

#### Acceptance Criteria

1. WHEN a user submits a login form with a valid email and matching password, THE Auth_Service SHALL return a JWT with an expiry duration of 15 to 60 minutes and a success response.
2. WHEN a user submits a login form with an email that does not exist in the Database, THE Auth_Service SHALL return an authentication error response without revealing whether the email or the password was incorrect.
3. WHEN a user submits a login form with a correct email but an incorrect password, THE Auth_Service SHALL return an authentication error response without revealing whether the email or the password was incorrect.
4. IF a user submits a login form with an incorrect email or password for 5 consecutive attempts, THEN THE Auth_Service SHALL reject all subsequent login attempts for that account for 15 minutes and return an error response indicating the account is temporarily locked.
5. THE Frontend SHALL store the JWT in a secure client-side storage location and include it as a Bearer token in the Authorization header of all subsequent requests to protected Backend endpoints.
6. WHEN a JWT expires, THE Auth_Service SHALL reject the request with an authentication error response indicating the session has expired and require the user to log in again.

### Requirement 3: User Logout

**User Story:** As an Authenticated_User, I want to log out of my account, so that my session is terminated and my data is protected on shared devices.

#### Acceptance Criteria

1. WHEN an Authenticated_User triggers a logout action, THE Frontend SHALL remove the stored JWT from client-side storage.
2. WHEN an Authenticated_User triggers a logout action, THE Backend SHALL invalidate the JWT server-side so that it cannot be reused after logout.
3. WHEN an Authenticated_User triggers a logout action, THE Frontend SHALL redirect the user to the login page.
4. IF the server-side JWT invalidation fails, THE Frontend SHALL still remove the JWT from client-side storage and redirect the user to the login page, and display an error message indicating the session may not have been fully terminated on the server.
5. WHILE an Authenticated_User is logged out, THE Frontend SHALL block access to all authenticated routes and redirect any navigation attempts to the login page.

### Requirement 4: Authorization and Data Isolation

**User Story:** As a user, I want assurance that no other user can access my personal data, so that my information remains private.

#### Acceptance Criteria

1. WHEN a request to any protected Backend endpoint is received without a valid JWT, THE Backend SHALL return a 401 Unauthorized response and SHALL NOT process the request further.
2. WHEN an Authenticated_User sends a request to read, modify, or delete a resource that belongs to a different user, THE Backend SHALL return a 403 Forbidden response and SHALL NOT modify any data belonging to either user.
3. THE Backend SHALL perform authorization checks on every protected endpoint to verify that the requesting Authenticated_User is the Owner of the requested resource before executing any read, write, or delete operation on that resource.
4. WHEN an incoming request contains data that fails schema validation, THE Backend SHALL return a 422 Unprocessable Entity response with an error message indicating which field(s) failed validation and why, and SHALL NOT persist or process the invalid data.
5. WHEN a JWT is present on a protected endpoint request, THE Backend SHALL reject the JWT and return a 401 Unauthorized response if the token is expired, structurally malformed, or signed with an unrecognized key.

---

### Requirement 5: Task Creation

**User Story:** As an Authenticated_User, I want to create a task with a title, priority, deadline, and category, so that I can track what I need to accomplish.

#### Acceptance Criteria

1. WHEN an Authenticated_User submits a task creation request with a title between 1 and 255 characters, THE Task_Manager SHALL persist a new Task record associated with that user and return the created Task including its generated identifier, title, priority, deadline, category, and creation timestamp.
2. IF an Authenticated_User submits a task creation request without a title or with a title exceeding 255 characters, THEN THE Task_Manager SHALL return a validation error response indicating the title constraint that was violated without persisting any data.
3. THE Task_Manager SHALL accept priority values of "low", "medium", or "high" for a Task, defaulting to "medium" when no priority value is provided; IF a priority value outside this set is provided, THEN THE Task_Manager SHALL return a validation error response indicating the accepted values without persisting any data.
4. THE Task_Manager SHALL accept an optional deadline as an ISO 8601 date value representing a calendar date; IF a malformed or non-date value is provided for the deadline field, THEN THE Task_Manager SHALL return a validation error response indicating the expected format without persisting any data.
5. IF an Authenticated_User submits a task creation request with a deadline date that is in the past relative to the current date, THEN THE Task_Manager SHALL return a validation error response indicating that the deadline must be a present or future date without persisting any data.
6. THE Task_Manager SHALL accept an optional category as a string between 1 and 100 characters; IF a category value is provided as an empty string or exceeds 100 characters, THEN THE Task_Manager SHALL return a validation error response indicating the category constraint that was violated without persisting any data.

### Requirement 6: Task Editing and Deletion

**User Story:** As an Authenticated_User, I want to edit and delete my tasks, so that I can keep my task list accurate and up to date.

#### Acceptance Criteria

1. WHEN an Authenticated_User submits a task update request for a Task the user owns, THE Task_Manager SHALL persist the updated fields (title, description, due date, priority, or status) and return the updated Task record reflecting all changes.
2. IF an Authenticated_User submits a task update request with a missing or empty title field, THEN THE Task_Manager SHALL reject the request and return an error response indicating the invalid field without modifying the existing Task record.
3. WHEN an Authenticated_User submits a task deletion request for a Task the user owns, THE Task_Manager SHALL permanently remove the Task record from the Database and return a success confirmation response.
4. IF an Authenticated_User submits a task update or deletion request for a Task the user does not own, THEN THE Task_Manager SHALL return a 403 Forbidden response without modifying any Task record.

### Requirement 7: Task Completion

**User Story:** As an Authenticated_User, I want to mark tasks as completed, so that I can track my progress through my workload.

#### Acceptance Criteria

1. WHEN an Authenticated_User marks a Task as completed, THE Task_Manager SHALL update the Task's completion status to "completed" and record the completion timestamp using the server-side current UTC time.
2. WHEN an Authenticated_User marks a completed Task as incomplete, THE Task_Manager SHALL update the Task's completion status to "incomplete" and clear the completion timestamp.
3. IF an Authenticated_User attempts to mark a Task as completed or incomplete for a Task that does not exist or is not owned by that user, THEN THE Task_Manager SHALL return an error response and leave the Task state unchanged.
4. IF an Authenticated_User marks a Task as completed when it is already completed, or as incomplete when it is already incomplete, THEN THE Task_Manager SHALL return a success response without modifying the Task record.

### Requirement 8: Task Querying

**User Story:** As an Authenticated_User, I want to view my tasks filtered by today's due date and overdue status, so that I can prioritize my day effectively.

#### Acceptance Criteria

1. WHEN an Authenticated_User requests today's tasks, THE Task_Manager SHALL return all incomplete Tasks owned by that user whose deadline matches the current calendar date in the user's local timezone.
2. WHEN an Authenticated_User requests overdue tasks, THE Task_Manager SHALL return all incomplete Tasks owned by that user whose deadline is earlier than the current calendar date in the user's local timezone.
3. THE Task_Manager SHALL return only Tasks owned by the requesting Authenticated_User.
4. IF no Tasks match the requested filter, THEN THE Task_Manager SHALL return an empty list rather than an error response.

---

### Requirement 9: Transaction Recording

**User Story:** As an Authenticated_User, I want to record income and expense transactions in IDR, so that I can track my personal cash flow.

#### Acceptance Criteria

1. WHEN an Authenticated_User submits a transaction creation request with a positive amount between 0.01 and 999,999,999,999.99, a type of "income" or "expense", a category of up to 100 characters, and a date in YYYY-MM-DD format, THE Finance_Manager SHALL persist the Transaction and return the created Transaction including its generated identifier, amount, type, category, date, and timestamp.
2. WHEN an Authenticated_User submits a transaction creation request with an optional description, THE Finance_Manager SHALL persist the description of up to 500 characters alongside the Transaction.
3. IF a transaction creation request is missing a required field (amount, type, category, or date), THEN THE Finance_Manager SHALL return a validation error response indicating which fields are missing without persisting any data.
4. IF a transaction creation request contains an amount that is zero or negative, THEN THE Finance_Manager SHALL return a validation error response indicating the amount must be a positive value without persisting any data.
5. IF a transaction creation request contains a type value other than "income" or "expense", THEN THE Finance_Manager SHALL return a validation error response indicating the accepted type values without persisting any data.
6. THE Finance_Manager SHALL store and display all monetary amounts in IDR with exactly two decimal places of precision.
7. WHEN an Authenticated_User submits a transaction deletion request for a Transaction owned by that user, THE Finance_Manager SHALL remove the Transaction record from the Database and return a success response.
8. IF an Authenticated_User submits a transaction deletion request for a Transaction not owned by that user, THEN THE Finance_Manager SHALL return an authorization error response without modifying any data.

### Requirement 10: Monthly Budget Management

**User Story:** As an Authenticated_User, I want to define a monthly budget in IDR, so that I can monitor my spending against a target.

#### Acceptance Criteria

1. WHEN an Authenticated_User submits a budget definition request with a positive IDR amount between 1 and 999,999,999,999 and a valid calendar month, THE Finance_Manager SHALL persist or update the Monthly_Budget for that user and month, and return the persisted Monthly_Budget including the amount and the calendar month.
2. IF an Authenticated_User submits a budget definition request with an amount less than or equal to 0, THEN THE Finance_Manager SHALL return a validation error response indicating the amount must be a positive value, without persisting any data.
3. IF an Authenticated_User submits a budget definition request with an amount exceeding 999,999,999,999, THEN THE Finance_Manager SHALL return a validation error response indicating the amount exceeds the maximum allowed value, without persisting any data.
4. IF an Authenticated_User submits a budget definition request with an invalid or missing calendar month, THEN THE Finance_Manager SHALL return a validation error response indicating the month field is invalid or missing, without persisting any data.
5. WHILE a Monthly_Budget exists for a given month, THE Finance_Manager SHALL compute the remaining budget as the Monthly_Budget amount minus the sum of all "expense" Transactions in that month owned by that user, where the remaining budget may be negative if total expenses exceed the Monthly_Budget amount.

### Requirement 11: Financial Summary

**User Story:** As an Authenticated_User, I want to view my monthly income, expenses, and remaining budget, so that I can understand my financial position at a glance.

#### Acceptance Criteria

1. WHEN an Authenticated_User requests a financial summary for a given month, THE Finance_Manager SHALL return the total income (sum of all "income" Transactions), total expenses (sum of all "expense" Transactions), and remaining budget (Monthly_Budget minus total expenses) for that month.
2. IF no transactions exist for the requested month, THE Finance_Manager SHALL return a summary with total income of 0, total expenses of 0, and a remaining budget equal to the Monthly_Budget amount if one is defined, or 0 if no budget is defined.
3. WHEN an Authenticated_User requests a spending breakdown for a given month, THE Finance_Manager SHALL return each unique expense category alongside the summed expense amount for that category in that month.
4. IF no expense transactions exist for the requested month, THE Finance_Manager SHALL return an empty category list rather than an error response.
5. THE Finance_Manager SHALL return only financial data owned by the requesting Authenticated_User.
6. THE System SHALL NOT provide financial advice, investment recommendations, or financial predictions in any user-facing text, tooltip, label, or computed value.

---

### Requirement 12: Learning Goal Management

**User Story:** As an Authenticated_User, I want to create and manage learning goals with target dates, so that I can organize my self-development efforts.

#### Acceptance Criteria

1. WHEN an Authenticated_User submits a learning goal creation request with a non-empty title of at most 200 characters and a valid ISO 8601 target date that is after the current date, THE Development_Tracker SHALL persist the Learning_Goal with an initial progress of 0% and return the created Learning_Goal.
2. IF an Authenticated_User submits a learning goal creation request without a title, with a title exceeding 200 characters, or with a target date that is not a valid ISO 8601 date or is not after the current date, THEN THE Development_Tracker SHALL return a validation error response indicating which field failed validation.
3. WHEN an Authenticated_User updates the progress percentage of a Learning_Goal the user owns with an integer value between 0 and 100 inclusive, THE Development_Tracker SHALL persist the updated progress and return the updated Learning_Goal.
4. IF an Authenticated_User provides a progress percentage outside the range 0–100, THEN THE Development_Tracker SHALL return a validation error response.
5. WHEN an Authenticated_User deletes a Learning_Goal the user owns, THE Development_Tracker SHALL remove the record from the Database and return a success response.
6. IF an Authenticated_User submits an update or delete request for a Learning_Goal that the user does not own, THEN THE Development_Tracker SHALL return an authorization error response and leave the Learning_Goal unchanged.

### Requirement 13: Learning Task Association

**User Story:** As an Authenticated_User, I want to create tasks linked to a learning goal, so that I can break down my goals into actionable steps.

#### Acceptance Criteria

1. WHEN an Authenticated_User creates a Task with a Learning_Goal identifier, IF the specified Learning_Goal exists and is owned by the Authenticated_User, THEN THE Task_Manager SHALL associate that Task with the specified Learning_Goal.
2. IF an Authenticated_User creates a Task with a Learning_Goal identifier that does not exist or is not owned by the Authenticated_User, THEN THE Task_Manager SHALL reject the Task creation and return an error indicating the Learning_Goal identifier is invalid or inaccessible.
3. WHEN an Authenticated_User requests Tasks associated with a specific Learning_Goal the user owns, THE Task_Manager SHALL return all Tasks linked to that Learning_Goal, or an empty list if no Tasks are associated.

### Requirement 14: Learning Progress Overview

**User Story:** As an Authenticated_User, I want to view all my active learning goals and their progress, so that I can stay aware of my development trajectory.

#### Acceptance Criteria

1. WHEN an Authenticated_User requests active learning goals, THE Development_Tracker SHALL return all Learning_Goals with a progress percentage below 100 that are owned by that user, including each goal's title, current progress percentage (0–99), and target completion date.
2. THE Development_Tracker SHALL return only Learning_Goals owned by the requesting Authenticated_User, excluding Learning_Goals owned by any other user regardless of shared access.
3. IF the requesting Authenticated_User has no active Learning_Goals, THEN THE Development_Tracker SHALL return an empty result set with an indication that no active goals exist.
4. THE System SHALL NOT present Learning_Goals or progress data as academic credentials, certifications, or professional qualifications.

---

### Requirement 15: Workout Session Recording

**User Story:** As an Authenticated_User, I want to manually record a workout session with its type, duration, and date, so that I can maintain a personal fitness log.

#### Acceptance Criteria

1. WHEN an Authenticated_User submits a workout session creation request with a non-empty workout type of up to 100 characters, a duration between 1 and 1440 minutes (inclusive), and a valid ISO 8601 date no later than the current date, THE Fitness_Tracker SHALL persist the Workout_Session and return the created Workout_Session record including its assigned identifier, workout type, duration, date, and any provided notes.
2. WHEN an Authenticated_User submits a workout session creation request with a duration less than 1 or greater than 1440 minutes, THE Fitness_Tracker SHALL return a validation error response indicating the duration constraint.
3. WHEN an Authenticated_User submits a workout session creation request without a workout type or with a workout type exceeding 100 characters, THE Fitness_Tracker SHALL return a validation error response indicating the workout type constraint.
4. THE Fitness_Tracker SHALL accept an optional notes field as a string of up to 500 characters for a Workout_Session.
5. IF an Authenticated_User submits a workout session creation request with a date that is in the future relative to the current date, THEN THE Fitness_Tracker SHALL return a validation error response indicating that the date must not be in the future.

### Requirement 16: Workout History and Weekly Summary

**User Story:** As an Authenticated_User, I want to view my workout history and a summary of this week's activity, so that I can track my fitness consistency.

#### Acceptance Criteria

1. WHEN an Authenticated_User requests workout history, THE Fitness_Tracker SHALL return all Workout_Sessions owned by that user sorted by session date in descending order.
2. WHEN an Authenticated_User requests the weekly activity summary, THE Fitness_Tracker SHALL return the count and total duration in whole minutes of Workout_Sessions owned by that user where the session date falls within the current ISO calendar week (Monday to Sunday).
3. THE Fitness_Tracker SHALL return only Workout_Sessions owned by the requesting Authenticated_User.
4. IF an Authenticated_User requests workout history and no Workout_Sessions exist for that user, THEN THE Fitness_Tracker SHALL return an empty list with a total count of zero.
5. IF an Authenticated_User requests the weekly activity summary and no Workout_Sessions exist within the current ISO calendar week, THEN THE Fitness_Tracker SHALL return a session count of zero and a total duration of zero minutes.
6. THE System SHALL NOT provide medical diagnoses, health assessments, or medical recommendations in any user-facing text or computed value.
7. THE System SHALL NOT integrate with GPS services, wearable devices, Apple Health, or Google Fit.

---

### Requirement 17: Security Checklist Management

**User Story:** As an Authenticated_User, I want to view and update a personal security checklist, so that I can track and improve my account security hygiene.

#### Acceptance Criteria

1. WHEN an Authenticated_User accesses the Security_Center for the first time, THE Security_Center SHALL initialize a Security_Checklist for that user containing exactly 5 items in the following order: "Two-Factor Authentication (2FA) enabled", "Password hygiene reviewed", "Recovery email address verified", "Active sessions reviewed", "Account security settings reviewed", each with an initial completion status of "unchecked".
2. WHEN an Authenticated_User marks a checklist item as complete, THE Security_Center SHALL update the completion status of that item to "checked" and persist the change within 2 seconds.
3. WHEN an Authenticated_User marks a checked item as incomplete, THE Security_Center SHALL update the completion status of that item to "unchecked" and persist the change within 2 seconds.
4. IF the completion status update for a checklist item fails to persist, THEN THE Security_Center SHALL display an error message indicating the save failed and retain the item's previous completion status in the displayed state.
5. THE Security_Center SHALL display the count of checked items and the total count of items as a progress indicator in the format "[checked count] / [total count]".
6. THE Security_Center SHALL NOT store, display, retrieve, or accept any password values.
7. THE System SHALL NOT present Security_Checklist items as a guarantee of security or as professional security advice.

---

### Requirement 18: Unified Dashboard Overview

**User Story:** As an Authenticated_User, I want to see a single dashboard that summarizes all five life areas after login, so that I can immediately understand what to focus on today.

#### Acceptance Criteria

1. WHEN an Authenticated_User loads the Dashboard, THE Dashboard SHALL display the following summary cards: today's tasks count and overdue tasks count, current month's financial summary (total income, total expenses, remaining budget), active learning goals count and average progress percentage (0–100%), this week's workout session count and total duration in minutes, and Security_Checklist completion progress as a percentage (0–100%).
2. WHEN any summary card contains no data for the Authenticated_User, THE Dashboard SHALL display an Empty_State for that card containing a descriptive message and a call-to-action link that navigates to the relevant module.
3. IF data for one or more summary cards fails to load, THEN THE Dashboard SHALL display an error indicator on each affected card and continue displaying successfully loaded cards without interruption.
4. THE Dashboard SHALL use a responsive card layout that renders in a single-column arrangement for viewport widths below 768px, a two-column arrangement for viewport widths between 768px and 1199px, and a three-or-more-column arrangement for viewport widths of 1200px and above.
5. THE Dashboard SHALL use a consistent visual design system — including typography, color palette, spacing scale, and iconography — across all five module cards.
6. THE Dashboard SHALL display the Life Score computed by the Life_Score_Engine for the Authenticated_User as a numeric value between 0 and 100.
7. WHEN an Authenticated_User clicks on a module card, THE Frontend SHALL navigate the user to the full detail view for that module.

---

### Requirement 19: Life Score Computation

**User Story:** As an Authenticated_User, I want to see a transparent Life Score that reflects my activity across all five areas, so that I can understand my overall engagement at a glance.

#### Acceptance Criteria

1. THE Life_Score_Engine SHALL compute a Life Score as an integer between 0 and 100 inclusive using only deterministic, rule-based arithmetic on the Authenticated_User's data; THE Life_Score_Engine SHALL NOT use machine learning models or AI inference.
2. THE Life_Score_Engine SHALL derive the Life Score by summing contributions from all five modules — task completion rate, budget adherence, learning goal progress, weekly workout activity, and Security_Checklist completion rate — where each module contributes equally at a maximum of 20 points, and each module's contribution is calculated as floor(module_ratio × 20), where module_ratio is a value between 0.0 and 1.0 representing that module's completion or adherence rate.
3. WHEN the Life_Score_Engine computes a Life Score, THE Dashboard SHALL display the total Life Score and a breakdown showing each of the five module names alongside its individual point contribution out of 20.
4. THE Frontend SHALL display explanatory text for each score component that identifies the input metric used (e.g., completion rate, adherence rate) and the formula applied to derive that component's contribution value.
5. THE System SHALL include a disclaimer stating that the Life Score is a personal productivity indicator only and does not constitute a medical, financial, psychological, or scientific assessment.
6. WHEN an Authenticated_User has no data in a module, THE Life_Score_Engine SHALL assign a contribution of 0 points for that module and SHALL still include that module in the breakdown display with a contribution value of 0.
7. IF the Life_Score_Engine cannot retrieve data from one or more modules due to a system error, THEN THE Dashboard SHALL display the last successfully computed Life Score with a notice indicating that the score may not reflect the latest activity, and THE Life_Score_Engine SHALL NOT display a partial score computed from fewer than five modules as if it were a full score.

---

### Requirement 20: Application Configuration and Security

**User Story:** As a developer deploying LifeGrid, I want all secrets and credentials managed via environment variables, so that no sensitive values are hardcoded in the source repository.

#### Acceptance Criteria

1. THE Backend SHALL read all secrets and credentials — including the database connection string, JWT signing secret, and any third-party API keys — exclusively from environment variables at runtime; IF any required environment variable is absent or empty at application startup, THEN THE Backend SHALL terminate immediately with an error message indicating which variable is missing, without starting the server.
2. THE System SHALL NOT include any secret values, credentials, or API keys as hardcoded literals in the source code, in committed configuration files, or in environment files (such as `.env`) tracked by version control; placeholder-only example environment files (containing no real secret values) are exempt from this restriction.
3. WHILE the Backend is running in a production deployment, THE Backend SHALL serve all API responses exclusively over HTTPS.
4. IF the Backend receives an HTTP request (non-HTTPS) in a production deployment, THEN THE Backend SHALL reject or redirect the request to its HTTPS equivalent without processing the original HTTP request.
5. THE Frontend SHALL communicate with the Backend exclusively through the defined REST API.
6. THE Frontend SHALL NOT access the Database directly.

### Requirement 21: Frontend Technology Constraints

**User Story:** As a developer building the LifeGrid frontend, I want a defined technology stack, so that the codebase is consistent and maintainable.

#### Acceptance Criteria

1. THE Frontend SHALL be implemented using React, TypeScript, Vite, and Tailwind CSS.
2. THE Frontend SHALL enforce TypeScript strict mode by enabling `strict: true` in the TypeScript configuration.
3. THE Frontend SHALL NOT use the `any` type unless accompanied by an inline comment beginning with `// justification:` explaining why `any` is necessary.
4. THE Frontend SHALL render all UI elements within the visible viewport on widths from 375px to 1440px without triggering horizontal scrolling.

### Requirement 22: Backend Technology Constraints

**User Story:** As a developer building the LifeGrid backend, I want a defined technology stack, so that the API is consistent and maintainable.

#### Acceptance Criteria

1. THE Backend SHALL be implemented using Python and FastAPI.
2. THE Backend SHALL use a monolithic architecture; THE Backend SHALL NOT be decomposed into separate microservices.
3. THE Backend SHALL use PostgreSQL as the sole persistent data store.
4. THE Backend SHALL define input and output schemas for all API endpoints using Pydantic models.
5. IF a request body, query parameter, or path parameter fails Pydantic model validation, THEN THE Backend SHALL reject the request with an error response indicating which fields failed validation without processing the request.
