"""WebSocket endpoints for bidirectional streaming queries and real-time push events."""

import json
import uuid

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from termnova.api.dependencies import get_settings
from termnova.api.ws_manager import ws_manager
from termnova.db.connection import AsyncSessionFactory, _create_async_engine
from termnova.rag.engine import RAGEngine

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/query")
async def websocket_query_endpoint(websocket: WebSocket):
    """Bidirectional streaming Q&A endpoint."""
    client_id = f"client_{uuid.uuid4().hex[:8]}"
    await ws_manager.connect(websocket, client_id)

    engine_instance = _create_async_engine()
    session_factory = AsyncSessionFactory(engine_instance)

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                payload = json.loads(raw_data)
            except Exception:
                await ws_manager.send_personal_message(
                    {"event": "error", "message": "Invalid JSON format payload"}, client_id
                )
                continue

            query_text = payload.get("query", "").strip()
            conv_id_str = payload.get("conversation_id")
            conv_id = uuid.UUID(conv_id_str) if conv_id_str else None

            if not query_text:
                await ws_manager.send_personal_message(
                    {"event": "error", "message": "Query cannot be empty"}, client_id
                )
                continue

            async with session_factory() as session:
                rag_engine = RAGEngine(session, settings=get_settings())

                try:
                    async for event_line in rag_engine.query_stream(
                        query_text, conversation_id=conv_id
                    ):
                        if event_line.startswith("data: "):
                            event_data = json.loads(event_line[6:].strip())
                            await ws_manager.send_personal_message(event_data, client_id)
                except Exception as e:
                    logger.error("Error in WS query streaming", error=str(e))
                    await ws_manager.send_personal_message(
                        {"event": "error", "message": str(e)}, client_id
                    )

    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
        logger.info("WebSocket query client disconnected", client_id=client_id)
    finally:
        await engine_instance.dispose()


@router.websocket("/ws/notifications")
async def websocket_notifications_endpoint(websocket: WebSocket):
    """Push notifications channel for ingestion and system events."""
    client_id = f"notif_{uuid.uuid4().hex[:8]}"
    await ws_manager.connect(websocket, client_id)

    try:
        await ws_manager.send_personal_message(
            {"event": "connected", "message": "Subscribed to Termnova push notifications"},
            client_id,
        )
        while True:
            # Keep connection open waiting for client ping/messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
        logger.info("WebSocket notifications client disconnected", client_id=client_id)
