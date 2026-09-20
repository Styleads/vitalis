from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/simulation")
async def simulation_websocket(websocket: WebSocket):

    await websocket.accept()

    print("WebSocket connected")

    try:
        await websocket.send_json({
            "message": "WebSocket is working"
        })

        while True:
            message = await websocket.receive_text()

            await websocket.send_json({
                "message": message
            })

    except WebSocketDisconnect:
        print("WebSocket disconnected")