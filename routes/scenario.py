from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/scenario",
    tags=["Scenario"]
)

current_scenario = "normal"

scenario_data = {
    "normal": {
        "additional_patients": 0,
        "available_beds": 20
    },
    "patient_surge": {
        "additional_patients": 20,
        "available_beds": 20
    },
    "resource_shortage": {
        "additional_patients": 0,
        "available_beds": 5
    },
    "equipment_failure": {
        "additional_patients": 0,
        "available_beds": 20,
        "available_equipment": 3
    }
}

ALLOWED_SCENARIOS = [
    "normal",
    "patient_surge",
    "resource_shortage",
    "equipment_failure"
]


@router.get("/")
def get_scenario():
    return {
        "current_scenario": current_scenario,
        "data": scenario_data[current_scenario]
    }


@router.post("/")
def trigger_scenario(scenario: str):

    global current_scenario

    if scenario not in ALLOWED_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario. Choose from: {ALLOWED_SCENARIOS}"
        )

    current_scenario = scenario

    return {
        "message": "Scenario triggered successfully",
        "current_scenario": current_scenario,
        "data": scenario_data[current_scenario]
    }