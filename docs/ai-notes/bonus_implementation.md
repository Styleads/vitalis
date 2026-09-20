# MedFlow Bonus Implementation & Project Status Guide

## 1. Current Project Status

| Component | Owner | Scope | Status | Verification / Tests |
| :--- | :--- | :--- | :---: | :--- |
| **Engine (`engine/`)** | **Person A** | Pure deterministic simulation engine, Slices 1–7, resource pools, invariants (I1–I10), CLI debug harness. | **100% DONE** | **89/89 PASSED** (including Erlang C M/M/c sanity checks) |
| **Strategies (`strategies/`)** | **Person B** | Allocation scoring, wait bonuses, starvation prevention, utilization penalties, Shortest-Service-First, hyperparameter tuning. | **100% DONE** | **35/35 PASSED** |
| **API Layer (`api/`)** | **Person C** | FastAPI REST endpoints, WebSocket live state streaming, scenario injectors, headless comparison runner. | **100% DONE** | **10/10 PASSED** |
| **Frontend (`frontend/`)** | **Person D** | React + TypeScript + Vite dashboard tabs, WebSocket live sync, scenario controls, comparison visuals. | **IN PROGRESS** | Building UI tabs |
| **AI / ML (`ml/`)** | **Bonus Track** | Synthetic patient data generator, triage urgency classifier, length-of-stay (LOS) regressor, AI hooks. | **READY TO BUILD** | Ready for implementation |

---

## 2. Bonus Features We Can Build Right Now (Backend & ML)

While Person D is finishing the frontend foundation, we can implement the following high-value bonus modules:

### Bonus 1: The Machine Learning Component (`ml/`)
We can implement the complete ML sub-package specified in `AGENT.md` Slice 9:
1. **`ml/synth.py`**: Seeded synthetic medical generator creating realistic clinical features:
   - Demographics: age, gender.
   - Vitals: systolic/diastolic blood pressure, heart rate, SpO2, respiratory rate, body temperature.
   - Clinical: chief complaint category, pain scale (1–10), comorbidities, high-risk flags.
2. **`ml/triage.py`**: Random Forest / Gradient Boosting classifier trained to predict clinical urgency tiers (1–5) from patient vitals and symptoms. Exposes deterministic `triage_fn(patient) -> int`.
3. **`ml/los.py`**: Gradient Boosting regressor predicting expected length of stay / service duration in seconds. Exposes deterministic `los_fn(patient) -> int`.
4. **`ml/evaluate.py`**: Generates confusion matrix, macro-F1, accuracy, and mean absolute error (MAE) for evaluation.
5. **`ml/README.md`**: Complete model card documenting generating assumptions, training methodology, and metrics for hackathon judges.

### Bonus 2: AI Hooks Integration in Simulation API
- Wire the trained `triage_fn` and `los_fn` into `api/sim_service.py` with an `enable_ai: bool` toggle in `POST /sim/start`.
- Expose `GET /ml/status` and `POST /ml/predict` endpoints for real-time inference inspection from the dashboard.

---

## 3. Clear Instructions to Give to Person D (Frontend)

Person D owns the presentation layer that the judges will interact with. Here are the exact instructions to hand over to Person D:

```markdown
### 📢 Instructions for Person D (Frontend / UI)

The backend (`http://localhost:8000`) and WebSocket (`ws://localhost:8000/ws/simulation`) are 100% ready, tested, and waiting for you. All endpoints are documented live at `http://localhost:8000/docs`.

#### 🎯 Core Tasks to Finish:
1. **Connect Live WebSocket**: Connect your dashboard to `ws://localhost:8000/ws/simulation` to receive real-time state envelopes (`{"type": "state", "data": snapshot}`).
2. **Implement the 9 Tabs**:
   - **Dashboard**: High-level KPI cards (Active Queue, In Treatment, Discharged, Interruptions, Utilization Gauges).
   - **Simulation**: Play / Pause / Resume buttons, Speed slider (0.1x – 10.0x), Step button (`POST /allocate`), Reset button.
   - **Patients**: Table showing Waiting and In-Treatment patients with color-coded urgency badges (1: Red, 2: Orange, 3: Yellow, 4: Blue, 5: Gray).
   - **Resources**: Resource grid showing BED, ICU_BED, OR, DOCTOR, NURSE status (Free: Green, Occupied: Blue, Failed: Red, Off: Gray).
   - **Analytics & Strategy**: Strategy switcher card (`POST /strategy`) and A/B comparison charts (`POST /compare`).
   - **Scenarios**: 3 quick-action buttons for Surge, Capacity change, and Resource failure (`POST /scenario/*`).
   - **Event Log**: Live scrolling event feed from `snapshot.recent_events`.
   - **Settings**: Seed selector and debug options.

#### 🌟 Bonus Features to Implement for Judge "WOW" Factor:
1. **Strategy A/B Comparison Visualizer (High Value)**:
   - Call `POST /compare` with `{"strategies": ["fifo", "urgency_only", "urgency_wait", "urgency_wait_utilization"]}`.
   - Render a side-by-side bar chart showing **Average Wait Time**, **Starvation Count**, and **P95 Wait Time** across the 4 strategies. Highlight how our advanced strategy eliminates starvation for urgent cases!
2. **Disruption Scenario Control Panel**:
   - Add 3 prominent "Chaos Engineering" buttons in the top navbar:
     - 🚨 **"Mass Casualty Surge (3x)"** -> calls `POST /scenario/surge {"multiplier": 3.0, "duration_s": 3600}`
     - ⚠️ **"Staff Strike (Doctor Capacity -50%)"** -> calls `POST /scenario/capacity {"type": "DOCTOR", "n": 4}`
     - 💥 **"ICU Power Failure"** -> calls `POST /scenario/fail {"unit_id": 21, "duration_s": 1800}`
   - Show a live toast/banner notification when a scenario is active.
3. **AI Triage & LOS Badges (ML Bonus)**:
   - When viewing patient details, display an **"AI Triage"** chip showing original triage vs model prediction, and a badge for **"Predicted LOS"**.
4. **Queue Contention & Starvation Warning**:
   - If a patient has been waiting > 4 hours, highlight their row with a pulsing orange warning badge ("Starvation Risk") to demonstrate our starvation-prevention algorithm.
```

---

## 4. Execution Step-by-Step

1. **Step 1**: Build the `ml/` package (`ml/synth.py`, `ml/triage.py`, `ml/los.py`, `ml/evaluate.py`, `ml/README.md`).
2. **Step 2**: Add tests in `tests/ml/` to ensure determinism, accuracy, and hook interface compliance.
3. **Step 3**: Connect the ML models to `api/sim_service.py` to allow running simulations with live AI triage and LOS predictions.
4. **Step 4**: Hand off the instructions to Person D and assist with frontend verification.
