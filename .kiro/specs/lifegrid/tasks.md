# Implementation Plan: LifeGrid

## Overview

LifeGrid is a full-stack personal life management dashboard built with React/TypeScript/Vite/Tailwind CSS on the frontend and Python/FastAPI/PostgreSQL on the backend. The implementation follows a strict dependency chain: infrastructure first, then backend domain modules, then frontend pages, and finally the full test suite.

Tasks 1–9 build the backend. Tasks 10–17 build the frontend. Tasks 18–20 cover the full property-based and integration test suite. Each task is sized to roughly 1–4 hours of focused implementation.

---

## Tasks

- [x] 1. Project scaffolding and configuration
  - [x] 1.1 Initialise the backend Python project
    - Create `backend/` directory with `pyproject.toml` or `requirements.txt` listing: `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `psycopg2-binary`, `alembic`, `pydantic[email]`, `pydantic-settings`, `python-jose[cryptography]`, `bcrypt`, `apscheduler`, `hypothesis`, `pytest`, `pytest-asyncio`, `httpx`
    - Create `backend/config.py` using `pydantic-settings` `BaseSettings`; declare `DATABASE_URL`, `JWT_SECRET`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `ALLOWED_ORIGINS` as required fields; add startup guard that terminates with a descriptive error if any required variable is absent
    - Create `backend/main.py` with the FastAPI app factory, CORS middleware (origins from config), and placeholder router includes
    - Create `backend/.env.example` with placeholder values only (no real secrets)
    - _Requirements: 20.1, 20.2, 22.1, 22.2_

  - [x] 1.2 Initialise the frontend project
    - Scaffold a Vite + React + TypeScript project under `frontend/`
    - Enable `strict: true` in `tsconfig.json`
    - Install and configure Tailwind CSS
    - Install `axios`, `react-router-dom@6`, `zustand`, `react-hook-form`, `zod`, `@hookform/resolvers`
    - Create `frontend/.env.example` with `VITE_API_BASE_URL=http://localhost:8000/api/v1`
    - _Requirements: 21.1, 21.2, 21.3, 20.2_


- [x] 2. Database schema and migrations (Alembic)
  - [x] 2.1 Set up Alembic and create initial migration
    - Run `alembic init backend/alembic` and point `sqlalchemy.url` to `DATABASE_URL` from env
    - Create `backend/database.py` with SQLAlchemy `engine`, `SessionLocal`, and `Base` declarative
    - Create `backend/dependencies.py` with `get_db()` generator dependency
    - _Requirements: 22.3, 20.1_

  - [x] 2.2 Define all ORM models and generate migration
    - Create `backend/models/user.py`: `users` table (`id` UUID PK, `email` VARCHAR 254 UNIQUE, `password_hash` VARCHAR 128, `failed_attempts` INTEGER default 0, `locked_until` TIMESTAMPTZ nullable, `created_at`, `updated_at`)
    - Create `backend/models/jwt_blocklist.py`: `jwt_blocklist` table with index on `expires_at`
    - Create `backend/models/task.py`: `tasks` table with all columns and indexes on `(user_id)`, `(user_id, deadline)`, `(user_id, status)`
    - Create `backend/models/finance.py`: `transactions` and `monthly_budgets` tables; unique constraint `(user_id, budget_year, budget_month)` on budgets; indexes on `(user_id, transaction_date)`
    - Create `backend/models/learning.py`: `learning_goals` table; indexes on `(user_id)`, `(user_id, progress_pct)`
    - Create `backend/models/fitness.py`: `workout_sessions` table; index on `(user_id, session_date)`
    - Create `backend/models/security.py`: `security_checklist_items` table; unique constraint `(user_id, item_order)`
    - Generate and apply migration: `alembic revision --autogenerate -m "initial_schema"` → `alembic upgrade head`
    - _Requirements: 20.1, 22.3; Design: Data Models section_


- [ ] 3. Backend: authentication module
  - [x] 3.1 Implement password hashing, JWT utilities, and auth schemas
    - Create `backend/services/auth_service.py`:
      - `hash_password(plain: str) -> str` using bcrypt cost factor ≥ 12
      - `verify_password(plain: str, hashed: str) -> bool` with timing-safe dummy check when email not found
      - `create_access_token(user_id: UUID, jti: str, expires_delta: timedelta) -> str` using HS256, reads `JWT_SECRET` from config
      - `decode_token(token: str) -> dict` — raises `HTTPException(401)` on expiry, malformation, or bad signature
    - Create `backend/schemas/auth.py`: `RegisterRequest`, `LoginRequest`, `TokenResponse`, `ErrorResponse` Pydantic models
    - _Requirements: 1.5, 1.6, 2.1, 2.6, 20.1; Design: JWT Structure, Password Security_

  - [x] 3.2 Implement JWT blocklist check and `get_current_user` dependency
    - In `auth_service.py` add `add_to_blocklist(jti, user_id, expires_at, db)` and `is_blocklisted(jti, db) -> bool`
    - Add APScheduler background job in `main.py` that runs hourly to `DELETE FROM jwt_blocklist WHERE expires_at < now()`
    - Update `backend/dependencies.py`: implement `get_current_user(token, db)` — decode JWT, check blocklist, fetch user, raise 401 on any failure
    - _Requirements: 3.2, 4.1, 4.5; Design: Logout and Server-Side Invalidation_

  - [x] 3.3 Implement login rate limiting
    - In `auth_service.py` add `check_rate_limit(email, db)` — reads `failed_attempts` and `locked_until` from `users`; returns `True` if locked
    - Add `increment_failure(email, db)` and `reset_failure(email, db)` helpers
    - Lock triggers when `failed_attempts` reaches 5; sets `locked_until = now() + 15min`
    - _Requirements: 2.4; Design: Login and Rate Limiting_

  - [-] 3.4 Implement auth router (`/api/v1/auth`)
    - Create `backend/routers/auth.py` with `POST /register`, `POST /login`, `POST /logout`
    - `POST /register`: validate → check duplicate email (409) → hash password → insert user → return 201 with JWT (exp=24h)
    - `POST /login`: check rate limit (423) → lookup user → dummy-check or real bcrypt → 401 on failure → reset counter + return 200 JWT (exp from config, 15–60 min)
    - `POST /logout`: `Depends(get_current_user)` → insert jti into blocklist → return 204
    - Include router in `main.py` under prefix `/api/v1`
    - _Requirements: 1.1–1.7, 2.1–2.6, 3.1–3.5, 4.1, 4.5_


- [ ] 4. Backend: task management module
  - [ ] 4.1 Implement task schemas and service
    - Create `backend/schemas/task.py`: `TaskCreate`, `TaskUpdate`, `TaskResponse`, `TaskListResponse` Pydantic models; include `@field_validator` for `deadline` (must not be in the past), `priority` enum (`low`/`medium`/`high` default `medium`), `category` (1–100 chars if provided), `title` (1–255 chars)
    - Create `backend/services/task_service.py`:
      - `create_task(data, user_id, db) -> Task`
      - `update_task(task_id, data, user_id, db) -> Task` — calls `require_owner`
      - `delete_task(task_id, user_id, db)` — calls `require_owner`
      - `set_completion(task_id, status, user_id, db) -> Task` — idempotent; sets/clears `completed_at` using server UTC; calls `require_owner`
      - `list_tasks(user_id, filter, learning_goal_id, db) -> list[Task]` — `filter` in `{today, overdue, all}`; today/overdue compare against server date
    - Implement `require_owner(resource_user_id, current_user_id)` utility in `dependencies.py` (raises 403 on mismatch)
    - _Requirements: 5.1–5.6, 6.1–6.4, 7.1–7.4, 8.1–8.4, 13.1–13.3_

  - [ ] 4.2 Implement tasks router (`/api/v1/tasks`)
    - Create `backend/routers/tasks.py` with all 7 endpoints listed in the design
    - All endpoints declare `current_user = Depends(get_current_user)`
    - Include router in `main.py`
    - _Requirements: 5.1–5.6, 6.1–6.4, 7.1–7.4, 8.1–8.4, 13.1–13.3_


- [ ] 5. Backend: personal finance module
  - [ ] 5.1 Implement finance schemas and service
    - Create `backend/schemas/finance.py`: `TransactionCreate`, `TransactionResponse`, `BudgetUpsert`, `BudgetResponse`, `FinancialSummaryResponse` (`total_income`, `total_expenses`, `remaining_budget`, `budget_amount`), `SpendingBreakdownItem`, `SpendingBreakdownResponse`; validators for `amount` (0.01–999_999_999_999.99), `type` enum (`income`/`expense`), `category` (1–100 chars), `transaction_date` (YYYY-MM-DD), `description` (≤500 chars)
    - Create `backend/services/finance_service.py`:
      - `create_transaction(data, user_id, db) -> Transaction`
      - `delete_transaction(tx_id, user_id, db)` — calls `require_owner`
      - `upsert_budget(year, month, amount, user_id, db) -> MonthlyBudget`
      - `get_budget(year, month, user_id, db) -> MonthlyBudget | None`
      - `compute_financial_summary(year, month, user_id, db) -> FinancialSummaryResponse` — all amounts stored/returned with 2dp; remaining_budget may be negative
      - `compute_spending_breakdown(year, month, user_id, db) -> list[SpendingBreakdownItem]`
    - _Requirements: 9.1–9.8, 10.1–10.5, 11.1–11.6_

  - [ ] 5.2 Implement finance router (`/api/v1/finance`)
    - Create `backend/routers/finance.py` with all 7 endpoints
    - Include router in `main.py`
    - _Requirements: 9.1–9.8, 10.1–10.5, 11.1–11.6_


- [ ] 6. Backend: personal development / learning module
  - [ ] 6.1 Implement learning schemas and service
    - Create `backend/schemas/learning.py`: `GoalCreate`, `GoalProgressUpdate`, `GoalResponse`; validators for `title` (1–200 chars), `target_date` (valid ISO 8601, must be strictly after today), `progress_pct` (integer 0–100)
    - Create `backend/services/learning_service.py`:
      - `create_goal(data, user_id, db) -> LearningGoal` — initial progress = 0
      - `update_progress(goal_id, progress_pct, user_id, db) -> LearningGoal` — calls `require_owner`
      - `delete_goal(goal_id, user_id, db)` — calls `require_owner`
      - `list_active_goals(user_id, db) -> list[LearningGoal]` — returns goals with `progress_pct < 100`
      - `validate_goal_ownership(goal_id, user_id, db)` — used by task service for learning task association (raises 400 if not found or not owned)
    - _Requirements: 12.1–12.6, 13.1–13.3, 14.1–14.4_

  - [ ] 6.2 Implement learning router (`/api/v1/learning`)
    - Create `backend/routers/learning.py` with 4 endpoints
    - Include router in `main.py`
    - _Requirements: 12.1–12.6, 14.1–14.4_


- [ ] 7. Backend: fitness module
  - [ ] 7.1 Implement fitness schemas and service
    - Create `backend/schemas/fitness.py`: `WorkoutCreate`, `WorkoutResponse`, `WeeklySummaryResponse` (`session_count`, `total_duration_minutes`, `week_start`, `week_end`); validators for `workout_type` (1–100 chars), `duration_minutes` (1–1440), `session_date` (valid date, not in the future), `notes` (≤500 chars)
    - Create `backend/services/fitness_service.py`:
      - `create_session(data, user_id, db) -> WorkoutSession`
      - `list_sessions(user_id, db) -> list[WorkoutSession]` — sorted by `session_date` DESC
      - `compute_weekly_summary(user_id, db) -> WeeklySummaryResponse` — ISO calendar week (Monday–Sunday); uses `date.isocalendar()` for boundary calculation; `total_duration_minutes` is an integer
    - _Requirements: 15.1–15.5, 16.1–16.7_

  - [ ] 7.2 Implement fitness router (`/api/v1/fitness`)
    - Create `backend/routers/fitness.py` with 3 endpoints
    - Include router in `main.py`
    - _Requirements: 15.1–15.5, 16.1–16.7_


- [ ] 8. Backend: personal security module
  - [ ] 8.1 Implement security schemas and service
    - Create `backend/schemas/security.py`: `ChecklistItemResponse`, `ChecklistResponse` (`items`, `checked_count`, `total_count`), `ChecklistToggleRequest` (`is_checked: bool`)
    - Create `backend/services/security_service.py`:
      - `get_or_init_checklist(user_id, db) -> list[SecurityChecklistItem]` — if no rows exist for user, bulk-insert exactly 5 items in order with labels: "Two-Factor Authentication (2FA) enabled", "Password hygiene reviewed", "Recovery email address verified", "Active sessions reviewed", "Account security settings reviewed"; all `is_checked = false`
      - `toggle_item(item_id, is_checked, user_id, db) -> SecurityChecklistItem` — calls `require_owner`; persists within a single transaction; on DB failure raises 500 (caller will return previous state per Req 17.4)
    - _Requirements: 17.1–17.7_

  - [ ] 8.2 Implement security router (`/api/v1/security`)
    - Create `backend/routers/security.py` with `GET /checklist` and `PATCH /checklist/{item_id}`
    - Include router in `main.py`
    - _Requirements: 17.1–17.7_


- [ ] 9. Backend: Life Score service and dashboard aggregation endpoint
  - [ ] 9.1 Implement Life Score service
    - Create `backend/services/life_score_service.py`:
      - `compute_module_ratio_tasks(user_id, db) -> float` — completed tasks / total tasks for current month; 0.0 if no tasks
      - `compute_module_ratio_finance(user_id, db) -> float` — `max(0, remaining_budget) / budget_amount`; 0.0 if no budget
      - `compute_module_ratio_learning(user_id, db) -> float` — average of `progress_pct / 100` across all active + recently completed goals; 0.0 if none
      - `compute_module_ratio_fitness(user_id, db) -> float` — `min(1.0, weekly_session_count / 5)`; 0.0 if no sessions this week
      - `compute_module_ratio_security(user_id, db) -> float` — `checked_count / 5`; 0.0 if checklist not initialized
      - `compute_life_score(ratios: list[float]) -> dict` — returns `{total, task_points, finance_points, learning_points, fitness_points, security_points}` using `floor(ratio × 20)` per module; total is always in [0, 100]
    - _Requirements: 19.1–19.7; Design: Life Score Calculation Algorithm_

  - [ ] 9.2 Implement dashboard schemas and router (`/api/v1/dashboard`)
    - Create `backend/schemas/dashboard.py`: `DashboardSummaryResponse` matching the full object shape from the design (life_score sub-object, tasks, finance, learning, fitness, security sub-objects, each with optional `error: true` flag); add `score_stale: bool` and `stale_modules: list[str]` fields on `life_score`
    - Create `backend/routers/dashboard.py` with `GET /dashboard/summary`:
      - Fetch each module's data independently inside a `try/except`; on failure set `error: True` for that sub-object and fall back to 0-contribution for Life Score
      - Return 200 always; never return a partial score as a full score (Req 19.7)
      - Include `score_stale: true` and `stale_modules` list when any module errored
    - Include router in `main.py`
    - _Requirements: 18.1–18.7, 19.1–19.7_

- [ ] 10. Checkpoint — verify full backend wiring
  - Ensure all tests pass, ask the user if questions arise.
  - Start `uvicorn backend.main:app --reload` and confirm `/docs` loads with all 7 router prefixes present
  - Confirm `alembic upgrade head` runs without error on a fresh DB


- [ ] 11. Frontend: shared components and design system
  - [ ] 11.1 Create TypeScript type definitions
    - Create `frontend/src/types/auth.types.ts`, `task.types.ts`, `finance.types.ts`, `learning.types.ts`, `fitness.types.ts`, `security.types.ts`, `dashboard.types.ts` — mirror all backend response schemas with TypeScript interfaces; use `no any` rule (Req 21.3)
    - _Requirements: 21.1–21.4_

  - [ ] 11.2 Build shared UI primitives
    - Create `frontend/src/components/shared/`: `Button.tsx`, `Input.tsx`, `Card.tsx`, `Modal.tsx`, `EmptyState.tsx`, `ErrorBoundary.tsx`, `ErrorCard.tsx`, `LoadingSpinner.tsx`, `Badge.tsx`, `ProgressBar.tsx`
    - All components must render correctly at viewport widths 375px–1440px without horizontal scroll (Req 21.4)
    - Use Tailwind CSS utility classes; define consistent typography, color palette, spacing, and iconography tokens in `tailwind.config.js`
    - _Requirements: 18.5, 21.1, 21.4; Design: Frontend Component Organization_

  - [ ] 11.3 Build layout components
    - Create `frontend/src/components/layout/AppLayout.tsx`, `Sidebar.tsx`, `TopBar.tsx`
    - `Sidebar` contains navigation links to all 5 module pages and the dashboard
    - `TopBar` shows user email and a logout button
    - _Requirements: 18.4, 18.5_


- [ ] 12. Frontend: auth pages, API client, and auth store
  - [ ] 12.1 Set up Axios client and auth store
    - Create `frontend/src/api/client.ts`: Axios instance with `baseURL` from `import.meta.env.VITE_API_BASE_URL`; request interceptor reads `lifegrid_token` from `localStorage` and sets `Authorization: Bearer <token>`; response interceptor clears token + redirects to `/login` on 401
    - Create `frontend/src/store/auth.store.ts` using Zustand: holds `token: string | null` and `setToken / clearToken` actions
    - Create `frontend/src/api/auth.ts`: `register(email, password)`, `login(email, password)`, `logout()` functions wrapping Axios calls
    - _Requirements: 2.5, 3.1, 3.3, 3.4; Design: Token Storage and Transport_

  - [ ] 12.2 Build `ProtectedRoute` and routing setup
    - Create `frontend/src/components/auth/ProtectedRoute.tsx`: reads `lifegrid_token`, decodes JWT payload without verifying signature, checks `exp`; redirects to `/login` if missing or expired; clears token on redirect
    - Create `frontend/src/router/index.tsx` with all routes from the design routing table; wrap `/app/*` routes with `ProtectedRoute`
    - Create `frontend/src/App.tsx` with `RouterProvider`
    - _Requirements: 3.3, 3.5; Design: Frontend Routing, Protected Route Guard_

  - [ ] 12.3 Build `LoginPage` and `RegisterPage`
    - Create `frontend/src/components/auth/LoginPage.tsx`: React Hook Form + Zod schema; on success store token + navigate to `/app/dashboard`; on 423 display lock message; on 401 display generic "Invalid credentials" (no email/password distinction)
    - Create `frontend/src/components/auth/RegisterPage.tsx`: validates password constraints (8–128 chars, ≥1 uppercase, ≥1 lowercase, ≥1 digit) inline; on 409 display "Email already in use"; on success store 24h token + navigate to `/app/dashboard`
    - Both pages map 422 field errors to inline field-level messages
    - _Requirements: 1.1–1.4, 1.6, 2.1–2.4; Design: Registration, Login and Rate Limiting_


- [ ] 13. Frontend: task management module
  - [ ] 13.1 Build task API layer and hook
    - Create `frontend/src/api/tasks.ts`: `createTask`, `listTasks(filter?, learning_goal_id?)`, `getTask`, `updateTask`, `deleteTask`, `completeTask`, `incompleteTask`
    - Create `frontend/src/hooks/useTasks.ts`: wraps API calls; returns `{tasks, isLoading, error, refetch}` and mutation functions; re-fetches after each mutation
    - _Requirements: 5.1–5.6, 6.1–6.4, 7.1–7.4, 8.1–8.4_

  - [ ] 13.2 Build task components and page
    - Create `TaskForm.tsx`: controlled form with title, priority select, deadline date picker, category input; Zod validation mirrors backend rules (title 1–255, priority enum, deadline not in past, category 1–100 if provided)
    - Create `TaskItem.tsx`: renders task with status toggle checkbox, edit and delete buttons; calls `completeTask`/`incompleteTask` on checkbox change
    - Create `TaskList.tsx`: renders list of `TaskItem` components; shows `EmptyState` when empty
    - Create `TaskFilters.tsx`: filter tabs for Today / Overdue / All; updates query param passed to `useTasks`
    - Create `TasksPage.tsx`: composes all task components; wraps in `ErrorBoundary`
    - _Requirements: 5.1–5.6, 6.1–6.4, 7.1–7.4, 8.1–8.4_


- [ ] 14. Frontend: personal finance module
  - [ ] 14.1 Build finance API layer and hook
    - Create `frontend/src/api/finance.ts`: `createTransaction`, `listTransactions`, `deleteTransaction`, `upsertBudget`, `getBudget`, `getFinancialSummary(year, month)`, `getSpendingBreakdown(year, month)`
    - Create `frontend/src/hooks/useFinance.ts`
    - _Requirements: 9.1–9.8, 10.1–10.5, 11.1–11.6_

  - [ ] 14.2 Build finance components and page
    - Create `TransactionForm.tsx`: amount (IDR, ≥0.01), type select, category, date, optional description (≤500 chars); Zod validation
    - Create `TransactionList.tsx`: lists transactions with delete button; shows `EmptyState` if empty
    - Create `BudgetForm.tsx`: single positive integer IDR amount + month picker; sends `PUT /finance/budgets/{year}/{month}`
    - Create `MonthlySummary.tsx`: displays `total_income`, `total_expenses`, `remaining_budget` formatted as IDR with 2dp; never shows financial advice (Req 11.6)
    - Create `SpendingBreakdown.tsx`: renders category breakdown as a list; shows `EmptyState` if no expense categories
    - Create `FinancePage.tsx`: composes all finance components; wraps in `ErrorBoundary`
    - _Requirements: 9.1–9.8, 10.1–10.5, 11.1–11.6_


- [ ] 15. Frontend: personal development / learning module
  - [ ] 15.1 Build learning API layer and hook
    - Create `frontend/src/api/learning.ts`: `createGoal`, `listActiveGoals`, `updateProgress(goalId, progress_pct)`, `deleteGoal`
    - Create `frontend/src/hooks/useLearning.ts`
    - _Requirements: 12.1–12.6, 13.1–13.3, 14.1–14.4_

  - [ ] 15.2 Build learning components and page
    - Create `GoalForm.tsx`: title (≤200 chars), target_date (ISO date, must be after today); Zod validation
    - Create `GoalItem.tsx`: displays title, `ProgressBar` with current percentage, edit progress button, delete button; progress input validates 0–100
    - Create `GoalList.tsx`: renders list of `GoalItem`; shows `EmptyState` if no active goals; does NOT display goals as credentials (Req 14.4)
    - Create `GoalTaskList.tsx`: renders tasks associated with a learning goal (calls `listTasks` with `learning_goal_id`)
    - Create `LearningPage.tsx`: composes all learning components; wraps in `ErrorBoundary`
    - _Requirements: 12.1–12.6, 13.1–13.3, 14.1–14.4_


- [ ] 16. Frontend: fitness module
  - [ ] 16.1 Build fitness API layer and hook
    - Create `frontend/src/api/fitness.ts`: `createSession`, `listSessions`, `getWeeklySummary`
    - Create `frontend/src/hooks/useFitness.ts`
    - _Requirements: 15.1–15.5, 16.1–16.7_

  - [ ] 16.2 Build fitness components and page
    - Create `WorkoutForm.tsx`: workout_type (1–100 chars), duration_minutes (1–1440), session_date (not in the future), optional notes (≤500 chars); Zod validation
    - Create `WorkoutList.tsx`: renders sessions sorted by date descending; shows `EmptyState` if empty; does NOT show medical advice (Req 16.6)
    - Create `WeeklySummary.tsx`: displays session count and total duration in minutes for the current ISO week; 0/0 if no sessions this week
    - Create `FitnessPage.tsx`: composes all fitness components; wraps in `ErrorBoundary`
    - _Requirements: 15.1–15.5, 16.1–16.7_


- [ ] 17. Frontend: personal security module
  - [ ] 17.1 Build security API layer and hook
    - Create `frontend/src/api/security.ts`: `getChecklist`, `toggleItem(itemId, is_checked)`
    - Create `frontend/src/hooks/useSecurity.ts`: on toggle failure, revert the local state to the previous `is_checked` value and display an error message (Req 17.4)
    - _Requirements: 17.1–17.7_

  - [ ] 17.2 Build security components and page
    - Create `ChecklistItem.tsx`: renders `item_label` and a checkbox; on change calls `toggleItem`; displays inline error if save fails; does NOT accept or display any password value (Req 17.6)
    - Create `ChecklistProgress.tsx`: displays progress as "[checked_count] / [total_count]" (Req 17.5); does NOT claim items guarantee security (Req 17.7)
    - Create `SecurityPage.tsx`: calls `getChecklist` on mount (auto-initializes for first-time users); composes `ChecklistProgress` and list of `ChecklistItem`; wraps in `ErrorBoundary`
    - _Requirements: 17.1–17.7_


- [ ] 18. Frontend: unified dashboard page and Life Score
  - [ ] 18.1 Build dashboard API layer and hook
    - Create `frontend/src/api/dashboard.ts`: `getDashboardSummary()` → maps to `DashboardSummaryResponse`
    - Create `frontend/src/hooks/useDashboard.ts`: single call to `GET /dashboard/summary`; surfaces per-card error flags
    - _Requirements: 18.1–18.7, 19.1–19.7_

  - [ ] 18.2 Build dashboard summary card components
    - Create `TasksSummaryCard.tsx`: shows today's task count and overdue count; `EmptyState` if no tasks; `ErrorCard` if error; clickable → navigates to `/app/tasks`
    - Create `FinanceSummaryCard.tsx`: shows total income, expenses, remaining budget for current month; `EmptyState` if no data; `ErrorCard` if error; clickable → `/app/finance`; no financial advice (Req 11.6)
    - Create `LearningSummaryCard.tsx`: shows active goal count and average progress %; `EmptyState` if no goals; clickable → `/app/learning`
    - Create `FitnessSummaryCard.tsx`: shows weekly session count and total duration; `EmptyState` if no sessions; does NOT show medical advice; clickable → `/app/fitness`
    - Create `SecuritySummaryCard.tsx`: shows checklist completion % as `checked/5 × 100`; clickable → `/app/security`
    - _Requirements: 18.1–18.7_

  - [ ] 18.3 Build `LifeScoreCard` component
    - Display total Life Score (0–100)
    - Display breakdown table: module name, input metric, formula, and points/20 for each of the 5 modules
    - Display explanatory text per component (Req 19.4)
    - Display disclaimer: "The Life Score is a personal productivity indicator only and does not constitute a medical, financial, psychological, or scientific assessment." (Req 19.5)
    - If `score_stale: true`, display notice: "Score may not reflect your latest activity"
    - _Requirements: 19.1–19.7_

  - [ ] 18.4 Build `DashboardPage` and responsive layout
    - Create `DashboardPage.tsx`: fetches via `useDashboard`; renders `LifeScoreCard` + all 5 summary cards
    - Apply responsive grid: single column below 768px, two columns 768–1199px, three-or-more columns ≥1200px (Req 18.4)
    - Each card failure renders `ErrorCard` without blocking others (Req 18.3)
    - _Requirements: 18.1–18.7_

- [ ] 19. Checkpoint — verify full frontend wiring
  - Ensure all tests pass, ask the user if questions arise.
  - Run `vitest --run` to confirm zero TypeScript errors
  - Manually navigate all 6 pages and verify no horizontal scroll at 375px viewport width


- [ ] 20. Property-based tests (hypothesis) for all 15 design properties
  - [ ] 20.1 Write property tests for auth validation (Properties 1–2)
    - Create `backend/tests/test_properties_auth.py`
    - **Property 1: Password Validation Rejects Any Non-Conforming Password** — `st.text()` generating strings shorter than 8, longer than 128, or missing a required character class; assert validator returns an error indicating the violated constraint
    - **Property 2: Password Validation Accepts Any Conforming Password** — `st.text()` filtered to 8–128 chars with ≥1 uppercase, ≥1 lowercase, ≥1 digit; assert validator returns no error
    - Tag each test: `# Feature: lifegrid, Property 1: ...` / `# Feature: lifegrid, Property 2: ...`
    - _Requirements: 1.3; Design: Property 1, Property 2_

  - [ ]* 20.2 Write property test for data ownership isolation (Property 3)
    - **Property 3: Data Ownership Isolation** — `st.uuids()` for `resource_user_id` and `current_user_id` where both are generated independently; assert `require_owner` raises 403 when they differ and raises no error when they are equal
    - _Requirements: 4.2, 6.4; Design: Property 3_

  - [ ]* 20.3 Write property tests for Life Score formula (Properties 4–5)
    - **Property 4: Life Score Formula Correctness** — `st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=5, max_size=5)`; assert `compute_life_score(ratios)` equals `sum(floor(r×20) for r in ratios)` and result is in [0, 100]
    - **Property 5: Life Score Zero Contribution for Empty Modules** — fix one or more ratios to 0.0; assert those modules contribute exactly 0 points and total is computed from all 5
    - _Requirements: 19.2, 19.6; Design: Property 4, Property 5_

  - [ ]* 20.4 Write property tests for financial aggregations (Properties 6–7)
    - **Property 6: Financial Summary Aggregation Correctness** — `st.lists(transaction_strategy)` where each transaction has type `income` or `expense` and a positive amount; assert `compute_financial_summary` returns correct `total_income`, `total_expenses`, and `remaining_budget`
    - **Property 7: Spending Breakdown Partition Correctness** — `st.lists(expense_transaction_strategy)`; assert exactly one entry per unique category, each entry's `total_amount` is the sum for that category, and sum of all totals equals `total_expenses`
    - _Requirements: 11.1, 10.5, 11.3; Design: Property 6, Property 7_

  - [ ]* 20.5 Write property tests for task filtering and completion toggle (Properties 8–10)
    - **Property 8: Task Date Filter Correctness** — `st.lists(task_strategy)` with `st.dates()`; assert today filter returns exactly incomplete tasks with deadline == today; overdue filter returns exactly incomplete tasks with deadline < today
    - **Property 9: Task Completion Toggle is a Round-Trip** — `st.builds(Task, status=st.just("incomplete"))`; mark complete then incomplete; assert status is `incomplete` and `completed_at` is `None`, all other fields unchanged
    - **Property 10: Idempotent Completion Operations** — `st.builds(Task, status=st.sampled_from(["incomplete","completed"]))`; repeat the same completion call twice; assert status and `completed_at` are unchanged after second call
    - _Requirements: 8.1, 8.2, 7.2, 7.4; Design: Property 8, Property 9, Property 10_

  - [ ]* 20.6 Write property tests for workout history and weekly summary (Properties 11–12)
    - **Property 11: Workout History Sort Order** — `st.lists(workout_session_strategy, min_size=0)`; assert returned list is sorted by `session_date` DESC and contains only sessions for the requesting user
    - **Property 12: Weekly Workout Summary Boundary Correctness** — `st.lists(workout_session_strategy)` with mixed dates inside and outside current ISO week; assert count and `total_duration_minutes` include only sessions within Monday–Sunday of current week
    - _Requirements: 16.1, 16.3, 16.2; Design: Property 11, Property 12_

  - [ ]* 20.7 Write property tests for learning goals filter and security checklist (Properties 13–14)
    - **Property 13: Active Learning Goals Filter Correctness** — `st.lists(goal_strategy)` with `progress_pct` drawn from `st.integers(min_value=0, max_value=100)`; assert only goals with `progress_pct` in [0, 99] are returned
    - **Property 14: Security Checklist Progress Indicator Correctness** — `st.lists(st.booleans(), min_size=5, max_size=5)`; assert `checked_count` equals count of `True` values and is in [0, 5]; `checked_count / 5` equals displayed progress
    - _Requirements: 14.1, 17.5; Design: Property 13, Property 14_

  - [ ]* 20.8 Write property test for transaction amount precision (Property 15)
    - **Property 15: Transaction Amount Precision Preservation** — `st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999999999.99"), places=2, allow_nan=False, allow_infinity=False)`; round-trip through `TransactionCreate` Pydantic schema and back; assert retrieved value equals original with exactly 2dp
    - _Requirements: 9.6; Design: Property 15_


- [ ] 21. Backend integration tests (pytest)
  - [ ] 21.1 Write auth integration tests
    - Create `backend/tests/test_auth.py` using `pytest` + `httpx` `AsyncClient`
    - Cover: registration success (201 + JWT), duplicate email (409), each password constraint violation (422), login success (200 + JWT), wrong password (401, opaque), nonexistent email (401, opaque), rate limit after 5 failures (423), logout (204), blocklisted token rejected (401), expired token rejected (401), missing token rejected (401)
    - _Requirements: 1.1–1.7, 2.1–2.6, 3.1–3.5, 4.1, 4.5_

  - [ ] 21.2 Write authorization and cross-user isolation integration tests
    - Cover: missing JWT → 401 on every protected endpoint; cross-user task read/update/delete → 403; cross-user transaction delete → 403; cross-user goal update/delete → 403; cross-user checklist toggle → 403
    - _Requirements: 4.1–4.5_

  - [ ]* 21.3 Write task management integration tests
    - Cover: create task happy path; title too long (422); bad priority (422); past deadline (422); bad category (422); update task; delete task; complete task (sets `completed_at`); uncomplete task (clears `completed_at`); idempotent complete; idempotent incomplete; filter=today; filter=overdue; filter=all; task linked to valid learning goal; task linked to nonexistent goal (400)
    - _Requirements: 5.1–5.6, 6.1–6.4, 7.1–7.4, 8.1–8.4, 13.1–13.3_

  - [ ]* 21.4 Write finance integration tests
    - Cover: create income transaction; create expense transaction; missing required field (422); zero amount (422); negative amount (422); bad type (422); delete own transaction (204); delete other's transaction (403); upsert budget; get budget; monthly summary with data; monthly summary without data; spending breakdown with expenses; spending breakdown without expenses
    - _Requirements: 9.1–9.8, 10.1–10.5, 11.1–11.6_

  - [ ]* 21.5 Write learning, fitness, and security integration tests
    - Learning: create goal; title too long (422); target_date in past (422); update progress 0–100; progress out of range (422); delete goal; list active goals (excludes progress=100); task association
    - Fitness: create session; duration < 1 (422); duration > 1440 (422); future session_date (422); list history (descending order); weekly summary in-week and cross-week
    - Security: first-access initializes 5 items; toggle checked; toggle unchecked; progress indicator value; toggle failure reverts state
    - _Requirements: 12.1–12.6, 13.1–13.3, 14.1–14.4, 15.1–15.5, 16.1–16.7, 17.1–17.7_

  - [ ]* 21.6 Write dashboard and Life Score integration tests
    - Cover: summary with all modules having data (all sub-objects populated, Life Score ≥ 0); summary with some modules having no data (those sub-objects return empty/zero values, score still computed from 5 modules); verify `life_score.total` equals sum of 5 module points; verify `score_stale` flag appears when a module errors; no partial score displayed as full score
    - _Requirements: 18.1–18.7, 19.1–19.7_


- [ ] 22. Frontend component tests (Vitest + React Testing Library)
  - [ ] 22.1 Write auth component tests
    - Create `frontend/src/components/auth/__tests__/ProtectedRoute.test.tsx`: no token → redirects to `/login`; valid unexpired token → renders children; expired token → redirects to `/login` and clears token
    - Create `LoginPage.test.tsx`: empty submit shows validation errors; valid submit stores token and navigates to dashboard; 423 response shows lock message; 401 response shows "Invalid credentials"
    - Create `RegisterPage.test.tsx`: password under 8 chars shows inline error; missing uppercase shows inline error; 409 response shows "Email already in use"; valid submit stores token and navigates
    - _Requirements: 1.1–1.4, 2.1–2.4, 3.3, 3.5_

  - [ ]* 22.2 Write shared component and Life Score tests
    - Create `ErrorBoundary.test.tsx`: child component that throws renders the fallback UI
    - Create `LifeScoreCard.test.tsx`: given mock score data renders correct total, correct per-module points, disclaimer text, and `score_stale` notice when flag is set
    - Create `EmptyState.test.tsx`: renders message and CTA text for each module context
    - _Requirements: 18.2, 19.3–19.5_

  - [ ]* 22.3 Write module page component tests
    - `TaskFilters.test.tsx`: clicking Today / Overdue / All updates query param correctly
    - `MonthlySummary.test.tsx`: renders IDR totals with 2dp; does not render any financial advice text
    - `ChecklistProgress.test.tsx`: renders correct `[checked]/[total]` format for all 0–5 checked states
    - `WeeklySummary.test.tsx`: renders session count and total duration for given data; renders 0/0 when no sessions
    - _Requirements: 8.1, 11.5, 17.5, 16.2_

- [ ] 23. Final checkpoint — full test suite passes
  - Ensure all tests pass, ask the user if questions arise.
  - Run `pytest backend/tests/ -v` — all tests green
  - Run `vitest --run` from `frontend/` — all tests green
  - Confirm no TypeScript strict errors (`tsc --noEmit`)


---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP; the core implementation tasks are never optional.
- Each task references specific requirements for traceability.
- Checkpoints (Tasks 10, 19, 23) ensure incremental validation at the backend, frontend, and final stages.
- Property tests (Task 20) validate universal correctness properties as defined in the design document's "Correctness Properties" section.
- Unit tests and property tests are complementary: property tests cover input-space breadth, integration tests cover concrete wiring and edge cases.
- The `require_owner` utility in `dependencies.py` is the single enforcement point for data isolation across all domain modules.
- All secret values must be read from environment variables; no secret should appear as a literal in any source file tracked by version control.
- The dashboard endpoint always returns HTTP 200, even when a module data fetch fails — error isolation is handled at the sub-object level.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["3.1"] },
    { "id": 4, "tasks": ["3.2", "3.3"] },
    { "id": 5, "tasks": ["3.4"] },
    { "id": 6, "tasks": ["4.1", "5.1", "6.1", "7.1", "8.1"] },
    { "id": 7, "tasks": ["4.2", "5.2", "6.2", "7.2", "8.2"] },
    { "id": 8, "tasks": ["9.1"] },
    { "id": 9, "tasks": ["9.2"] },
    { "id": 10, "tasks": ["11.1"] },
    { "id": 11, "tasks": ["11.2", "11.3"] },
    { "id": 12, "tasks": ["12.1"] },
    { "id": 13, "tasks": ["12.2"] },
    { "id": 14, "tasks": ["12.3"] },
    { "id": 15, "tasks": ["13.1", "14.1", "15.1", "16.1", "17.1"] },
    { "id": 16, "tasks": ["13.2", "14.2", "15.2", "16.2", "17.2"] },
    { "id": 17, "tasks": ["18.1"] },
    { "id": 18, "tasks": ["18.2", "18.3"] },
    { "id": 19, "tasks": ["18.4"] },
    { "id": 20, "tasks": ["20.1", "21.1", "21.2"] },
    { "id": 21, "tasks": ["20.2", "20.3", "20.4", "20.5", "20.6", "20.7", "20.8", "21.3", "21.4", "21.5"] },
    { "id": 22, "tasks": ["21.6", "22.1"] },
    { "id": 23, "tasks": ["22.2", "22.3"] }
  ]
}
```
