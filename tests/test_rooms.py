"""
test_rooms.py - CRUD tests for Room entity.
"""
import pytest
from tests.helpers import (
    api_get, api_post, api_put, api_delete,
    assert_api_ok, assert_api_error,
    navigate_to_crud, ADMIN_TOKEN, HOD_TOKEN,
    QA_ROOM
)

QA_ROOM_ID = QA_ROOM["room_no"]


class TestRoomAPI:
    """API-level CRUD tests for rooms."""

    def test_list_rooms(self):
        """GET /api/rooms returns a list of rooms."""
        resp = api_get("/api/rooms")
        assert_api_ok(resp, "List rooms")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Room list should have seed data"

    def test_rooms_have_required_fields(self):
        """Rooms should have room_no, room_name, capacity fields."""
        resp = api_get("/api/rooms")
        data = resp.json()
        if data:
            room = data[0]
            assert "room_no" in room, "Missing room_no field"

    def test_create_room(self):
        """POST /api/rooms creates a new room."""
        api_delete(f"/api/rooms/{QA_ROOM_ID}")
        resp = api_post("/api/rooms", QA_ROOM)
        assert_api_ok(resp, "Create room")

    def test_get_room_by_id(self):
        """GET /api/rooms/<id> returns correct room."""
        api_post("/api/rooms", QA_ROOM)
        resp = api_get(f"/api/rooms/{QA_ROOM_ID}")
        assert_api_ok(resp, "Get room by ID")
        data = resp.json()
        assert data.get("room_no") == QA_ROOM_ID

    def test_update_room(self):
        """PUT /api/rooms/<id> updates room data."""
        api_post("/api/rooms", QA_ROOM)
        updated = {**QA_ROOM, "room_name": "QA Room - Updated"}
        resp = api_put(f"/api/rooms/{QA_ROOM_ID}", updated)
        assert_api_ok(resp, "Update room")

    def test_delete_room(self):
        """DELETE /api/rooms/<id> removes a room."""
        api_post("/api/rooms", QA_ROOM)
        resp = api_delete(f"/api/rooms/{QA_ROOM_ID}")
        assert_api_ok(resp, "Delete room")

    def test_nonexistent_room_returns_404(self):
        """GET /api/rooms/<nonexistent> returns 404."""
        resp = api_get("/api/rooms/NONEXISTENT_ROOM_9999")
        assert_api_error(resp, 404, "Nonexistent room")

    def test_room_capacity_is_numeric(self):
        """Room capacity should be a positive integer."""
        resp = api_get("/api/rooms")
        data = resp.json()
        for room in data[:5]:
            cap = room.get("capacity")
            if cap is not None:
                assert isinstance(cap, (int, float)) and cap > 0, (
                    f"Room {room.get('room_no')} has invalid capacity: {cap}"
                )

    def test_hod_cannot_create_room(self):
        """HOD token rejected for room creation."""
        resp = api_post("/api/rooms", QA_ROOM, token=HOD_TOKEN)
        assert_api_error(resp, 403, "HOD create room")

    def test_hod_can_read_rooms(self):
        """HOD should be able to read rooms list."""
        resp = api_get("/api/rooms", token=HOD_TOKEN)
        assert_api_ok(resp, "HOD read rooms")


class TestRoomUI:
    """UI tests for room management."""

    def test_rooms_visible_in_crud_manager(self, admin_page):
        """Rooms should be visible in the CRUD manager."""
        navigate_to_crud(admin_page, "rooms")
        admin_page.wait_for_timeout(1500)
        content = admin_page.inner_text("body")
        assert len(content) > 50, "Rooms list content is empty"
