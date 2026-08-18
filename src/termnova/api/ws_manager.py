"""WebSocket connection manager for bidirectional streaming and push notifications."""

import json
from typing import Any

import structlog
from fastapi import WebSocket

from termnova.observability.metrics import ACTIVE_CONNECTIONS

logger = structlog.get_logger(__name__)


class WebSocketManager:
    """Manages active WebSocket connections and channel-based broadcasting."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.channel_members: dict[
            str, set[str]
        ] = {}  # channel_id (workspace_id) -> set of client_ids

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept connection and register client."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        ACTIVE_CONNECTIONS.set(len(self.active_connections))
        logger.info(
            "WebSocket client connected", client_id=client_id, total=len(self.active_connections)
        )

    def disconnect(self, client_id: str) -> None:
        """Unregister client on disconnect and clean up channel memberships."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            ACTIVE_CONNECTIONS.set(len(self.active_connections))

        # Clean up channel memberships
        for channel_id in list(self.channel_members.keys()):
            self.channel_members[channel_id].discard(client_id)
            if not self.channel_members[channel_id]:
                del self.channel_members[channel_id]

        logger.info(
            "WebSocket client disconnected",
            client_id=client_id,
            remaining=len(self.active_connections),
        )

    async def join_channel(self, client_id: str, channel_id: str) -> None:
        """Subscribe a connected client to a workspace channel."""
        if channel_id not in self.channel_members:
            self.channel_members[channel_id] = set()
        self.channel_members[channel_id].add(client_id)
        logger.debug("Client joined workspace channel", client_id=client_id, channel_id=channel_id)

    async def leave_channel(self, client_id: str, channel_id: str) -> None:
        """Unsubscribe client from a workspace channel."""
        if channel_id in self.channel_members:
            self.channel_members[channel_id].discard(client_id)
            if not self.channel_members[channel_id]:
                del self.channel_members[channel_id]
        logger.debug("Client left workspace channel", client_id=client_id, channel_id=channel_id)

    async def broadcast_to_channel(self, channel_id: str, message: dict[str, Any]) -> None:
        """Send message to all clients subscribed to a specific workspace channel."""
        members = list(self.channel_members.get(channel_id, set()))
        if not members:
            return

        payload = json.dumps(message)
        dead_clients = []

        for cid in members:
            ws = self.active_connections.get(cid)
            if ws:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead_clients.append(cid)

        for cid in dead_clients:
            self.disconnect(cid)

    async def send_personal_message(self, message: dict[str, Any], client_id: str) -> None:
        """Send JSON message to a specific client."""
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                await ws.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(
                    "Failed to send WebSocket message", client_id=client_id, error=str(e)
                )
                self.disconnect(client_id)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast message to all connected clients."""
        payload = json.dumps(message)
        dead_clients = []

        for cid, ws in self.active_connections.items():
            try:
                await ws.send_text(payload)
            except Exception:
                dead_clients.append(cid)

        for cid in dead_clients:
            self.disconnect(cid)

    async def broadcast_ingestion_progress(
        self,
        document_id: str,
        filename: str,
        status: str,
        progress: float = 1.0,
    ) -> None:
        """Broadcast document parsing/vectorizing progress."""
        await self.broadcast(
            {
                "event": "ingestion_progress",
                "data": {
                    "document_id": document_id,
                    "filename": filename,
                    "status": status,
                    "progress": progress,
                },
            }
        )


ws_manager = WebSocketManager()
