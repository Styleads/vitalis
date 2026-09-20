# medflow-backend/
# │
# ├── venv/
# │
# ├── app/
# │   ├── __init__.py
# │   ├── main.py
# │   │
# │   ├── routes/
# │   │   ├── __init__.py
# │   │   ├── patients.py
# │   │   ├── resources.py
# │   │   ├── stats.py
# │   │   ├── strategy.py
# │   │   └── scenario.py
# │   │
# │   ├── models/
# │   │   ├── __init__.py
# │   │   └── schemas.py
# │   │
# │   ├── services/
# │   │   ├── __init__.py
# │   │   ├── simulation.py
# │   │   └── scenario_service.py
# │   │
# │   └── websocket/
# │       ├── __init__.py
# │       └── manager.py
# │
# └── requirements.txt
# 

from fastapi import FastAPI
from routes import (
    patients,
    resources,
    stats,
    strategy,
    scenario,
    simulation,
    websocket,
    allocate
)
app = FastAPI(
    title="MedFlow API",
    description="Backend API for MedFlow",
    version="1.0.0"
)


app.include_router(patients.router)
app.include_router(resources.router)
app.include_router(stats.router)
app.include_router(strategy.router)
app.include_router(scenario.router)
app.include_router(simulation.router)
app.include_router(websocket.router)
app.include_router(allocate.router)


@app.get("/")
def root():
    return {
        "message": "MedFlow Backend is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }