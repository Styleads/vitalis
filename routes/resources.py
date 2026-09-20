from fastapi import APIRouter
import routes.scenario as scenario

router = APIRouter(
    prefix="/resources",
    tags=["Resources"]
)


@router.get("/")
def get_resources():

    beds_available = 20
    equipment_available = 8

    if scenario.current_scenario == "resource_shortage":
        beds_available = 5

    if scenario.current_scenario == "equipment_failure":
        equipment_available = 3

    return {
        "scenario": scenario.current_scenario,

        "beds": {
            "total": 50,
            "available": beds_available,
            "occupied": 50 - beds_available
        },

        "doctors": {
            "total": 10,
            "available": 5,
            "busy": 5
        },

        "equipment": {
            "total": 15,
            "available": equipment_available,
            "in_use": 15 - equipment_available
        }
    }