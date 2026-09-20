from fastapi import APIRouter
import routes.scenario as scenario

router = APIRouter(
    prefix="/stats",
    tags=["Statistics"]
)


@router.get("/")
def get_stats():

    patients_waiting = 12
    patients_treated = 35
    average_wait_time = 14
    beds_available = 20
    equipment_available = 8

    if scenario.current_scenario == "patient_surge":
        patients_waiting = 32
        average_wait_time = 22

    elif scenario.current_scenario == "resource_shortage":
        beds_available = 5
        average_wait_time = 20

    elif scenario.current_scenario == "equipment_failure":
        equipment_available = 3
        average_wait_time = 18

    return {
        "scenario": scenario.current_scenario,
        "patients_waiting": patients_waiting,
        "patients_treated": patients_treated,
        "average_wait_time": average_wait_time,
        "beds_available": beds_available,
        "equipment_available": equipment_available
    }