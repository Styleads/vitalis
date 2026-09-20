# Implementation Plan: Connect Frontend to Backend

## Context & Current State
We conducted a comprehensive audit of `AGENT.md`, the spec files, and all project directories:
1. **Engine (`engine/`)**: 100% complete and tested (89/89 tests passing). Implements pure deterministic discrete-event simulation, atomic resource reservation (`try_reserve`), backfill continuation, and scenario hooks (`inject_surge`, `set_capacity`, `fail_resource`).
2. **Strategies (`strategies/`)**: 100% complete and tested (35/35 tests passing). Implements `urgency_only`, `urgency_wait`, `urgency_wait_utilization`, `shortest_service_first`, display statistics transformation, and strategy comparison.
3. **Backend API (`api/`)**: 100% complete and tested (10/10 tests passing). FastAPI app running with CORS, full REST routers (`/sim`, `/patients`, `/resources`, `/stats`, `/strategy`, `/scenario`, `/compare`, `/demo`, `/allocate`), background wall-clock tick loop (`sim_service.py`), and live WebSocket streaming on `/ws/simulation`.
4. **Frontend (`frontend/`)**: Currently has a complete React + TypeScript dashboard with rich UI components, but is running exclusively on local mock state (`useState(initialResources)`, `useState(initialPatients)`, local `setInterval` clock, local mock scenarios).

Our goal is to **connect the frontend to the backend** so that the dashboard is driven live by the real simulation engine via WebSocket state broadcasts and REST control endpoints.

---

## User Review Required

> [!IMPORTANT]
> - **Port Conventions**: Backend serves on `http://localhost:8000` (WebSocket at `ws://localhost:8000/ws/simulation`), and Frontend Vite dev server runs on `http://localhost:5173`.
> - **Data Transformation**: The backend snapshot represents resources with keys `BED`, `ICU_BED`, `OR`, `DOCTOR`, `NURSE`, `AMBULANCE`, and time in integer seconds (`clock`, `wait_s`). We will preserve the frontend's visual component contracts by mapping snapshot data directly into UI models with human-readable timestamps (`HH:MM:SS` and `Xm`) and friendly names ("Beds", "ICU Beds", etc.).
> - **Fallback & Resilience**: If the backend is temporarily offline or booting up, the UI will display a connection badge ("Connecting..." / "Offline") and fall back gracefully rather than crashing.

---

## Proposed Changes

### Frontend Integration Layer

#### [NEW] [api.ts](file:///c:/Users/Kruthik/Desktop/coding/vitalis/frontend/src/api.ts)
Create a centralized API client module:
- **Base URLs**: Configurable REST base URL (`http://localhost:8000`) and WebSocket URL (`ws://localhost:8000/ws/simulation`).
- **REST Endpoints**:
  - `startSimulation(params)`: `POST /sim/start`
  - `pauseSimulation()`: `POST /sim/pause`
  - `resumeSimulation()`: `POST /sim/resume`
  - `setSimulationSpeed(speed)`: `POST /sim/speed`
  - `resetSimulation(params)`: `POST /sim/reset`
  - `getSimulationStatus()`: `GET /sim/status`
  - `getSimulationState()`: `GET /state`
  - `getStats()`: `GET /stats`
  - `getStrategies()`: `GET /strategy`
  - `setStrategy(name)`: `POST /strategy`
  - `triggerSurge(multiplier, duration_s)`: `POST /scenario/surge`
  - `adjustCapacity(type, n)`: `POST /scenario/capacity`
  - `failResource(unit_id, duration_s)`: `POST /scenario/fail`
  - `compareStrategies(params)`: `POST /compare`
  - `getDemoScenarios()`: `GET /demo/scenarios`
  - `loadDemoScenario(name)`: `POST /demo/load`
  - `manualAllocate()`: `POST /allocate`
- **WebSocket Manager**:
  - `connectWebSocket(handlers)`: Manages WebSocket lifecycle, auto-reconnect on close/error, dispatches incoming `state`, `events`, `stats`, and connection status changes.

---

#### [MODIFY] [types.ts](file:///c:/Users/Kruthik/Desktop/coding/vitalis/frontend/src/types.ts)
Expand frontend types to declare backend snapshot interfaces and mapping types:
- Add `BackendResourceType`: `"BED" | "ICU_BED" | "OR" | "DOCTOR" | "NURSE" | "AMBULANCE"`.
- Add `Snapshot`, `QueueItem`, `TreatmentItem`, `PoolState`, `LogEvent`, `DisplayStats`, `ComparisonResult`.
- Provide data conversion helpers:
  - `mapSnapshotToPatients(queue, clock)` -> transforms backend queue to UI `Patient[]`
  - `mapSnapshotToTreatment(in_treatment, clock)` -> transforms in-treatment patients to UI `TreatmentPatient[]`
  - `mapSnapshotToResources(resources)` -> transforms pool counts to UI `Resource[]`
  - `mapSnapshotToEvents(recent_events)` -> formats engine logs into UI `EventItem[]`
  - `formatSimSeconds(seconds)` -> formats simulated seconds to `HH:MM:SS`

---

#### [MODIFY] [App.tsx](file:///c:/Users/Kruthik/Desktop/coding/vitalis/frontend/src/App.tsx)
Wire up all UI components to backend services:
1. **WebSocket Connection Hook**:
   - Establish live WebSocket connection on mount.
   - On `"state"` message: update `clock`, `patients`, `in_treatment`, `resources`, `events`, `strategy`, `flags`.
   - Update connection status badge in the topbar (🟢 Connected / 🟡 Reconnecting / 🔴 Offline).
2. **Simulation Controls**:
   - **Start / Resume**: Call `resumeSimulation()` or `startSimulation()`.
   - **Pause**: Call `pauseSimulation()`.
   - **Reset**: Call `resetSimulation()`.
   - **Speed (0.5x, 1x, 2x, 4x)**: Call `setSimulationSpeed(speedMultiplier)`.
3. **Strategy Switching & Real Comparison**:
   - Fetch available strategies from `GET /strategy` and set active strategy via `setStrategy(name)`.
   - Fetch real comparison metrics from `POST /compare` across all 3 primary strategies (`urgency_only`, `urgency_wait`, `urgency_wait_utilization`) to populate the Strategy Comparison cards with actual simulation outcomes (avg wait, utilization, treated, starvation).
4. **Scenario Controls & Demo Scenarios**:
   - "Emergency Surge" -> Call `triggerSurge(3.0, 3600)`.
   - "Staff Shortage" -> Call `adjustCapacity("NURSE", 6)`.
   - "Resource Failure" -> Call `failResource(unitId, 1800)`.
   - "Normal Operations" -> Call `resetSimulation()`.
   - Named Demo buttons ("Queue Jump", "ICU Contention", "Starvation", "Surge Demo", "Full Demo") -> Call `loadDemoScenario(scenarioKey)`.
5. **Real-time Analytics Chart**:
   - Capture dynamic time series points `(time, wait, utilization)` as ticks arrive from the backend to animate the AreaChart with real simulation progression.
6. **Live KPI Cards & System Integrity**:
   - Derive live Treated, Waiting, In Treatment, and Interrupted counts directly from backend stats and snapshot.
   - Display true Capacity Violations (0) and Resource Conflicts (0) guaranteed by the engine invariants.

---

## Verification Plan

### Automated Tests
1. **Backend Test Suite**:
   ```powershell
   python -m pytest -q
   ```
   Ensure all 134+ tests pass cleanly.
2. **Frontend TypeCheck & Build**:
   ```cmd
   cmd.exe /c "npm run build"
   ```
   Ensure TypeScript compilation and Vite production bundle succeed without errors.

### End-to-End Manual Verification
1. Start FastAPI backend with `python -m uvicorn api.main:app --port 8000`.
2. Verify frontend connects to WebSocket (`ws://localhost:8000/ws/simulation`).
3. Press **Start**: verify clock advances, events stream in, queue re-ranks dynamically.
4. Press **Emergency Surge**: verify arrival multiplier spikes and new patients stream in.
5. Click **Strategy Selection**: switch between `urgency_only` and `urgency_wait_utilization`, verifying instant queue re-sorting.
6. Click **Demo Scenarios** ("Queue Jump", "ICU Contention"): verify scenario loads and runs deterministically.
