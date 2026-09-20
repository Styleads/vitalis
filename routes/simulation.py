from fastapi import APIRouter
from services.simulation_engine import simulation_engine

router = APIRouter(
    prefix="/simulation",
    tags=["Simulation"]
)


@router.get("/")
def get_simulation():

    return simulation_engine.get_state()


@router.post("/tick")
def simulation_tick():

    result = simulation_engine.run_tick()

    return {
        "message": "Simulation tick completed",
        "simulation": result
    }