from fastapi import APIRouter

router = APIRouter(
    prefix="/allocate",
    tags=["Allocation"]
)


@router.post("/")
def allocate_resource(
    patient_id: str,
    resource_type: str
):
    return {
        "message": "Allocation request received",
        "patient_id": patient_id,
        "resource_type": resource_type,
        "status": "pending"
    }