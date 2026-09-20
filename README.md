# Vitalis — Hospital Resource Management Simulator

Vitalis is a real-time hospital resource management simulator powered by the **MedFlow** discrete-event simulation engine.

---

## 🚀 How to Run the Entire Project (Backend + Frontend)

To run the project, open **two terminal windows** (or PowerShell tabs) in the project root directory `vitalis`.

### Terminal 1: Backend (FastAPI + Engine)

Run the FastAPI backend server using Python and `uvicorn`:

```bash
python -m uvicorn api.main:app --reload --port 8000
```

- **API Documentation**: Open `http://localhost:8000/docs` in your browser.
- **WebSocket Endpoint**: `ws://localhost:8000/ws/simulation`
- **Health Check**: `http://localhost:8000/health`

---

### Terminal 2: Frontend (React + Vite)

Navigate into the `frontend` folder and start the Vite development server:

```bash
cd frontend
npm run dev
```

*(Note: On Windows PowerShell if script execution is restricted, run `cmd /c "npm run dev"` or `npx vite`)*

- **Dashboard UI**: Open `http://localhost:5173` in your browser.

---

## 🧪 Running Automated Verification Tests

### Run Backend Unit & Invariant Tests
```bash
python -m pytest -q
```

### Build Frontend Production Bundle
```bash
cd frontend
npm run build
```

---

## 🏗️ System Architecture

- **`engine/`**: Pure deterministic discrete-event simulation core (Python standard library only).
- **`strategies/`**: Pluggable priority scoring algorithms (`urgency_only`, `urgency_wait`, `urgency_wait_utilization`).
- **`api/`**: FastAPI REST control service, WebSocket state broadcaster (`/ws/simulation`), and headless comparison engine.
- **`frontend/`**: React + TypeScript + Vite live dashboard with real-time telemetry, scenario injection, and A/B strategy comparison visuals.