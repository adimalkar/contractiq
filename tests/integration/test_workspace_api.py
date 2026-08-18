"""Integration tests for Collaborative Workspace REST endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_workspace_crud_and_chat_lifecycle(api_client: AsyncClient):
    """End-to-end test creating a workspace, sending messages, querying AI, and pinning."""
    # 1. Create Workspace
    create_resp = await api_client.post(
        "/api/v1/workspaces/",
        json={
            "name": "Integration Test Room",
            "description": "Testing collaborative RAG",
            "document_scope": [],
            "created_by": "TestUser",
        },
    )
    assert create_resp.status_code == 201
    ws_data = create_resp.json()
    ws_id = ws_data["id"]
    assert ws_data["name"] == "Integration Test Room"
    assert ws_data["member_count"] == 1

    # 2. List Workspaces
    list_resp = await api_client.get("/api/v1/workspaces/")
    assert list_resp.status_code == 200
    workspaces = list_resp.json()
    assert any(w["id"] == ws_id for w in workspaces)

    # 3. Add Member
    add_member_resp = await api_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_name": "Bob Lawyer", "role": "editor"},
    )
    assert add_member_resp.status_code == 200
    assert add_member_resp.json()["user_name"] == "Bob Lawyer"

    # 4. Send Human Message
    msg_resp = await api_client.post(
        f"/api/v1/workspaces/{ws_id}/messages",
        json={"user_name": "Bob Lawyer", "content": "Checking indemnification sections."},
    )
    assert msg_resp.status_code == 200
    msg_data = msg_resp.json()
    msg_id = msg_data["id"]
    assert msg_data["content"] == "Checking indemnification sections."

    # 5. Pin Message
    pin_resp = await api_client.patch(
        f"/api/v1/workspaces/{ws_id}/messages/{msg_id}",
        json={"is_pinned": True},
    )
    assert pin_resp.status_code == 200
    assert pin_resp.json()["is_pinned"] is True

    # 6. Check Pinned List
    pinned_resp = await api_client.get(f"/api/v1/workspaces/{ws_id}/pinned")
    assert pinned_resp.status_code == 200
    pinned_list = pinned_resp.json()
    assert len(pinned_list) == 1
    assert pinned_list[0]["id"] == msg_id

    # 7. Add Reaction
    react_resp = await api_client.patch(
        f"/api/v1/workspaces/{ws_id}/messages/{msg_id}",
        json={"reaction": "👍", "user_name": "TestUser"},
    )
    assert react_resp.status_code == 200
    assert "TestUser" in react_resp.json()["reactions"]["👍"]

    # 8. Query Workspace AI
    query_resp = await api_client.post(
        f"/api/v1/workspaces/{ws_id}/query",
        json={"query": "Summarize key terms", "user_name": "TestUser"},
    )
    assert query_resp.status_code == 200
    q_data = query_resp.json()
    assert q_data["human_message"]["content"] == "Summarize key terms"
    assert q_data["ai_response"]["message_type"] == "ai_response"
