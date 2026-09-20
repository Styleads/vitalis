# Walkthrough: Connecting Frontend to Backend

We have connected the **Vitalis React Frontend** to the **MedFlow FastAPI Simulation Engine** via live WebSocket streaming (`/ws/simulation`) and REST control endpoints.

---

## What Was Accomplished

### 1. Data Contract & Adapter Layer ([`types.ts`](file:///c:/Users/Kruthik/Desktop/coding/vitalis/frontend/src/types.ts))
- Declared full TypeScript schemas for backend types: `Snapshot`, `QueueItem`, `TreatmentItem`, `PoolState`, `LogEvent`, `DisplayStats`, `ComparisonResult`, `BackendResourceType` (`BED`, `ICU_BED`, `OR`, `DOCTOR`, `NURSE`, `AMBULANCE`).
- Added robust data mapping helpers to seamlessly transform backend data into existing frontend UI component models:
  - `mapSnapshotToPatients`: Maps engine queue items with integer seconds into UI `Patient` records with simulated arrival times (`HH:MM:SS`) and wait durations (`Xm`).
  - `mapSnapshotToTreatment`: Maps in-treatment patients into department, care team, and progress percentage.
  - `mapSnapshotToResources`: Maps atomic pools into friendly resource categories (`Beds`, `ICU Beds`, `Operating Rooms`, `Doctors`, `Nurses`, `Ambulances`) with occupied, free, failed, and off counts.
  - `mapSnapshotToEvents`: Maps engine events (`ARRIVAL`, `ASSIGNED`, `DISCHARGED`, `FAILURE`, `RECOVERY`, `SURGE_START`, `CAPACITY_CHANGE`) into formatted feed items.

### 2. Centralized API & WebSocket Client ([`api.ts`](file:///c:/Users/Kruthik/Desktop/coding/vitalis/frontend/src/api.ts))
- Implemented full typed REST client functions matching all backend endpoints:
  - Simulation lifecycle: `startSimulation`, `pauseSimulation`, `resumeSimulation`, `setSimulationSpeed`, `resetSimulation`, `getSimulationStatus`, `getSimulationState`, `getStats`.
  - Strategy management: `getStrategies`, `setStrategy`, `compareStrategies`.
  - Operational scenarios: `triggerSurge`, `adjustCapacity`, `failResource`.
  - Scripted demos: `getDemoScenarios`, `loadDemoScenario`.
  - Manual step: `manualAllocate`.
- Implemented resilient WebSocket manager `connectSimulationSocket`:
  - Connects to `ws://localhost:8000/ws/simulation`.
  - Dispatches incoming `state`, `events`, and `stats` messages directly to state callbacks.
  - Features exponential backoff auto-reconnect if the connection drops.
  - Exposes socket connection status (`connected`, `connecting`, `disconnected`).

### 3. Live Dashboard Integration ([`App.tsx`](file:///c:/Users/Kruthik/Desktop/coding/vitalis/frontend/src/App.tsx) & [`styles.css`](file:///c:/Users/Kruthik/Desktop/coding/vitalis/frontend/src/styles.css))
- **Header Status Badge**: Shows live connection state (`🟢 Engine Connected` / `🟡 Connecting...` / `🔴 Engine Offline`).
- **Simulation Control Strip**:
  - **Start / Pause / Resume**: Directly controls engine clock progression through REST calls.
  - **Reset**: Resets engine to clean deterministic baseline.
  - **Step**: Runs manual step and allocation pass when paused.
  - **Speed Multiplier**: Toggles speed between 0.5x, 1.0x, 2.0x, and 4.0x.
- **Dynamic KPI Cards**:
  - Live Treated Patients, Waiting Count, In Treatment, Interrupted (P-FAIL count), Avg Wait Time, and System Utilization calculated directly from real simulation engine metrics.
- **Pluggable Strategy Selection & A/B Comparison**:
  - Fetches real `/compare` output to display live comparative metrics (average wait time, utilization, treated count, starvation count) across `Urgency Only`, `Urgency + Wait`, and `Urgency + Wait + Utilization`.
  - Clicking a strategy card hot-swaps the active strategy via `POST /strategy` and immediately re-ranks the queue.
- **Scenario Injection Buttons**:
  - Emergency Surge: injects a 3x Poisson arrival burst for 1 hour.
  - Staff Shortage: reduces nurse capacity to 6 with graceful `pending_off` semantics.
  - Resource Failure: simulates ICU bed failure with automatic P-FAIL patient requeuing.
  - Normal Operations: restores baseline pool capacity and resets queue.
- **Scripted Demo Scenarios**:
  - Direct 1-click loading of named demo seeds: `Queue Jump`, `ICU Contention`, `Starvation`, `Surge Demo`, and `Full Demo`.
- **Telemetry Charts**:
  - Real-time `AreaChart` streams simulated time against average wait time and capacity utilization.
- **System Integrity Card**:
  - Proves 0 Capacity Violations (I3) and 0 Double-Booking Conflicts (I2) guaranteed by engine invariants.

---

## Verification Results

### 1. Frontend Production Build
```cmd
cmd.exe /c "npm run build"
```
```
vite v6.4.3 building for production...
✓ 2199 modules transformed.
dist/index.html                   0.79 kB │ gzip:   0.44 kB
dist/assets/index-D7WAXyKM.css   20.72 kB │ gzip:   5.09 kB
dist/assets/index-DqgOlRFR.js   586.67 kB │ gzip: 168.67 kB
✓ built in 6.81s
Exit Code: 0
```

### 2. Backend Automated Test Suite
```powershell
python -m pytest -q
```
```
134 passed, 20 subtests passed in 20.68s
Exit Code: 0
```
All engine invariants, strategy scoring tests, REST endpoints, and WebSocket connection tests passed with 100% success.
