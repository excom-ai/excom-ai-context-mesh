"""Unit tests for StateManager and backends."""

import pytest

from contextmesh.core.context import RuntimeContext
from contextmesh.core.models import APIResponse, StateUpdate
from contextmesh.execution.state_manager import InMemoryStateBackend, StateManager


class TestInMemoryStateBackend:
    """Tests for InMemoryStateBackend."""

    @pytest.fixture
    def backend(self):
        """Create a backend instance."""
        return InMemoryStateBackend()

    def test_write_creates_record(self, backend):
        """Test that write creates a new record."""
        update = StateUpdate(
            operation="write",
            table="test_table",
            values={"id": "123", "name": "Test"},
        )
        result = backend.write(update)
        assert result is True

        # Verify record exists
        record = backend.read("test_table", {"id": "123"})
        assert record is not None
        assert record["name"] == "Test"

    def test_write_multiple_records(self, backend):
        """Test writing multiple records to same table."""
        update1 = StateUpdate(
            operation="write",
            table="items",
            values={"id": "1", "value": "first"},
        )
        update2 = StateUpdate(
            operation="write",
            table="items",
            values={"id": "2", "value": "second"},
        )
        backend.write(update1)
        backend.write(update2)

        records = backend.read_all("items")
        assert len(records) == 2

    def test_read_returns_first_match(self, backend):
        """Test that read returns first matching record."""
        backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"category": "A", "value": "first"},
        ))
        backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"category": "A", "value": "second"},
        ))

        record = backend.read("items", {"category": "A"})
        assert record["value"] == "first"

    def test_read_returns_none_for_no_match(self, backend):
        """Test that read returns None when no match."""
        backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"id": "1"},
        ))

        record = backend.read("items", {"id": "999"})
        assert record is None

    def test_read_returns_none_for_empty_table(self, backend):
        """Test that read returns None for empty table."""
        record = backend.read("nonexistent", {"id": "1"})
        assert record is None

    def test_read_all_returns_all_records(self, backend):
        """Test read_all returns all records."""
        for i in range(3):
            backend.write(StateUpdate(
                operation="write",
                table="items",
                values={"id": str(i)},
            ))

        records = backend.read_all("items")
        assert len(records) == 3

    def test_read_all_with_query(self, backend):
        """Test read_all with query filter."""
        backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"category": "A", "id": "1"},
        ))
        backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"category": "B", "id": "2"},
        ))
        backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"category": "A", "id": "3"},
        ))

        records = backend.read_all("items", {"category": "A"})
        assert len(records) == 2

    def test_update_modifies_matching_records(self, backend):
        """Test that update modifies matching records."""
        backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"id": "1", "status": "pending"},
        ))

        update = StateUpdate(
            operation="update",
            table="items",
            values={"status": "completed"},
            condition={"id": "1"},
        )
        result = backend.update(update)
        assert result is True

        record = backend.read("items", {"id": "1"})
        assert record["status"] == "completed"

    def test_update_returns_false_for_no_match(self, backend):
        """Test update returns False when no records match."""
        backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"id": "1"},
        ))

        update = StateUpdate(
            operation="update",
            table="items",
            values={"status": "completed"},
            condition={"id": "999"},
        )
        result = backend.update(update)
        assert result is False

    def test_delete_removes_matching_records(self, backend):
        """Test that delete removes matching records."""
        backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"id": "1"},
        ))
        backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"id": "2"},
        ))

        result = backend.delete("items", {"id": "1"})
        assert result is True

        records = backend.read_all("items")
        assert len(records) == 1
        assert records[0]["id"] == "2"

    def test_delete_returns_false_for_no_match(self, backend):
        """Test delete returns False when no records match."""
        backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"id": "1"},
        ))

        result = backend.delete("items", {"id": "999"})
        assert result is False

    def test_clear_table(self, backend):
        """Test clearing a specific table."""
        backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"id": "1"},
        ))
        backend.write(StateUpdate(
            operation="write",
            table="other",
            values={"id": "2"},
        ))

        backend.clear("items")

        assert backend.read_all("items") == []
        assert len(backend.read_all("other")) == 1

    def test_clear_all(self, backend):
        """Test clearing all tables."""
        backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"id": "1"},
        ))
        backend.write(StateUpdate(
            operation="write",
            table="other",
            values={"id": "2"},
        ))

        backend.clear()

        assert backend.read_all("items") == []
        assert backend.read_all("other") == []


class TestStateManager:
    """Tests for StateManager."""

    @pytest.fixture
    def manager(self):
        """Create a state manager with in-memory backend."""
        return StateManager(InMemoryStateBackend())

    @pytest.fixture
    def context(self):
        """Create a runtime context."""
        return RuntimeContext({
            "state": {"case_id": "CASE-123"},
            "db": {"customer": {"id": "CUST-456"}},
        })

    @pytest.fixture
    def success_response(self):
        """Create a success API response."""
        return APIResponse(
            status_code=200,
            body={"adjustmentId": "ADJ-789", "amount": 100.00},
            headers={},
            success=True,
        )

    @pytest.fixture
    def failure_response(self):
        """Create a failure API response."""
        return APIResponse(
            status_code=400,
            body={"error": "Bad request"},
            headers={},
            success=False,
            error="Bad request",
        )

    def test_apply_updates_on_success(self, manager, context, success_response):
        """Test applying updates on success."""
        state_updates = {
            "onSuccess": [
                {
                    "write": {
                        "table": "adjustment_log",
                        "values": {
                            "case_id": "{{state.case_id}}",
                            "adjustment_id": "{{response.adjustmentId}}",
                        },
                    }
                }
            ]
        }

        updates = manager.apply_updates(state_updates, context, success_response)

        assert len(updates) == 1
        assert updates[0].operation == "write"
        assert updates[0].table == "adjustment_log"

        # Verify data was written
        record = manager.backend.read("adjustment_log", {"case_id": "CASE-123"})
        assert record is not None
        assert record["adjustment_id"] == "ADJ-789"

    def test_apply_updates_on_failure(self, manager, context, failure_response):
        """Test applying updates on failure."""
        state_updates = {
            "onSuccess": [
                {"write": {"table": "success_log", "values": {"status": "ok"}}}
            ],
            "onFailure": [
                {"write": {"table": "error_log", "values": {"status": "failed"}}}
            ],
        }

        updates = manager.apply_updates(state_updates, context, failure_response)

        assert len(updates) == 1
        assert updates[0].table == "error_log"

        # Verify only failure update was written
        assert manager.backend.read("success_log", {}) is None
        assert manager.backend.read("error_log", {"status": "failed"}) is not None

    def test_apply_updates_always(self, manager, context, success_response):
        """Test applying 'always' updates."""
        state_updates = {
            "always": [
                {"write": {"table": "audit_log", "values": {"event": "api_call"}}}
            ]
        }

        updates = manager.apply_updates(state_updates, context, success_response)

        assert len(updates) == 1
        assert updates[0].table == "audit_log"

    def test_apply_updates_resolves_templates(self, manager, context, success_response):
        """Test that templates are resolved."""
        state_updates = {
            "onSuccess": [
                {
                    "write": {
                        "table": "log",
                        "values": {
                            "customer": "{{db.customer.id}}",
                            "response_amount": "{{response.amount}}",
                        },
                    }
                }
            ]
        }

        manager.apply_updates(state_updates, context, success_response)

        record = manager.backend.read("log", {})
        assert record["customer"] == "CUST-456"
        assert record["response_amount"] == 100.00

    def test_update_history_tracked(self, manager, context, success_response):
        """Test that update history is tracked."""
        state_updates = {
            "onSuccess": [
                {"write": {"table": "log1", "values": {"id": "1"}}},
                {"write": {"table": "log2", "values": {"id": "2"}}},
            ]
        }

        manager.apply_updates(state_updates, context, success_response)

        history = manager.get_history()
        assert len(history) == 2

    def test_clear_history(self, manager, context, success_response):
        """Test clearing update history."""
        state_updates = {
            "onSuccess": [
                {"write": {"table": "log", "values": {"id": "1"}}}
            ]
        }

        manager.apply_updates(state_updates, context, success_response)
        assert len(manager.get_history()) == 1

        manager.clear_history()
        assert len(manager.get_history()) == 0

    def test_apply_update_operation(self, manager, context, success_response):
        """Test applying an update operation."""
        # First write a record
        manager.backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"id": "1", "status": "pending"},
        ))

        state_updates = {
            "onSuccess": [
                {
                    "update": {
                        "table": "items",
                        "values": {"status": "completed"},
                        "condition": {"id": "1"},
                    }
                }
            ]
        }

        manager.apply_updates(state_updates, context, success_response)

        record = manager.backend.read("items", {"id": "1"})
        assert record["status"] == "completed"

    def test_apply_delete_operation(self, manager, context, success_response):
        """Test applying a delete operation."""
        # First write a record
        manager.backend.write(StateUpdate(
            operation="write",
            table="items",
            values={"id": "1"},
        ))

        state_updates = {
            "onSuccess": [
                {
                    "delete": {
                        "table": "items",
                        "condition": {"id": "1"},
                    }
                }
            ]
        }

        manager.apply_updates(state_updates, context, success_response)

        record = manager.backend.read("items", {"id": "1"})
        assert record is None
