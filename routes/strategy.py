from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/strategy",
    tags=["Strategy"]
)

current_strategy = "fifo"

ALLOWED_STRATEGIES = [
    "fifo",
    "priority",
    "shortest_wait"
]

# Dummy patients for simulation
patients = [
    {
        "id": "P001",
        "severity": "low",
        "wait_time": 10
    },
    {
        "id": "P002",
        "severity": "high",
        "wait_time": 5
    },
    {
        "id": "P003",
        "severity": "medium",
        "wait_time": 20
    }
]


@router.get("/")
def get_strategy():
    return {
        "current_strategy": current_strategy
    }


@router.post("/")
def set_strategy(strategy: str):
    global current_strategy

    if strategy not in ALLOWED_STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy. Choose from: {ALLOWED_STRATEGIES}"
        )

    current_strategy = strategy

    return {
        "message": "Strategy updated successfully",
        "current_strategy": current_strategy
    }


@router.get("/simulate")
def simulate_strategy():

    if current_strategy == "fifo":
        selected_patient = patients[0]

    elif current_strategy == "priority":
        selected_patient = max(
            patients,
            key=lambda patient: {
                "high": 3,
                "medium": 2,
                "low": 1
            }[patient["severity"]]
        )

    elif current_strategy == "shortest_wait":
        selected_patient = min(
            patients,
            key=lambda patient: patient["wait_time"]
        )

    return {
        "strategy": current_strategy,
        "selected_patient": selected_patient
    }