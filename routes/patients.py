from fastapi import APIRouter
import routes.scenario as scenario

router = APIRouter(
    prefix="/patients",
    tags=["Patients"]
)

base_patients = [
    {
        "id": "P001",
        "severity": "high",
        "status": "waiting"
    },
    {
        "id": "P002",
        "severity": "medium",
        "status": "treated"
    },
    {
        "id": "P003",
        "severity": "low",
        "status": "waiting"
    }
]


@router.get("/")
def get_patients():

    patients = base_patients.copy()

    if scenario.current_scenario == "patient_surge":

        additional_patients = scenario.scenario_data[
            "patient_surge"
        ]["additional_patients"]

        for i in range(additional_patients):

            patients.append({
                "id": f"P{len(patients) + 1:03}",
                "severity": "medium",
                "status": "waiting"
            })

    return {
        "scenario": scenario.current_scenario,
        "total_patients": len(patients),
        "patients": patients
    }