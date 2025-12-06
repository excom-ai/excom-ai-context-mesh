"""Unit tests for RuntimeContext."""

import pytest

from contextmesh.core.context import ContextNamespace, RuntimeContext
from contextmesh.utils.exceptions import ContextPathError


class TestContextNamespace:
    """Tests for ContextNamespace."""

    def test_init_empty(self):
        """Test initializing empty namespace."""
        ns = ContextNamespace("db")
        assert ns.to_dict() == {}

    def test_init_with_data(self):
        """Test initializing with data."""
        data = {"customer": {"id": "123"}}
        ns = ContextNamespace("db", data)
        assert ns.to_dict() == data

    def test_get_simple_path(self):
        """Test getting a simple path."""
        ns = ContextNamespace("db", {"customer_id": "123"})
        assert ns.get("customer_id") == "123"

    def test_get_nested_path(self):
        """Test getting a nested path."""
        ns = ContextNamespace("db", {"customer": {"id": "123", "name": "John"}})
        assert ns.get("customer.id") == "123"
        assert ns.get("customer.name") == "John"

    def test_get_deeply_nested(self):
        """Test getting deeply nested path."""
        ns = ContextNamespace("db", {"a": {"b": {"c": {"d": "value"}}}})
        assert ns.get("a.b.c.d") == "value"

    def test_get_missing_path_raises(self):
        """Test that missing path raises error."""
        ns = ContextNamespace("db", {"customer": {"id": "123"}})
        with pytest.raises(ContextPathError):
            ns.get("customer.missing")

    def test_set_simple_path(self):
        """Test setting a simple path."""
        ns = ContextNamespace("db")
        ns.set("customer_id", "123")
        assert ns.get("customer_id") == "123"

    def test_set_nested_path(self):
        """Test setting a nested path creates structure."""
        ns = ContextNamespace("db")
        ns.set("customer.id", "123")
        assert ns.get("customer.id") == "123"

    def test_set_overwrites_existing(self):
        """Test that set overwrites existing value."""
        ns = ContextNamespace("db", {"value": "old"})
        ns.set("value", "new")
        assert ns.get("value") == "new"

    def test_has_existing_path(self):
        """Test has returns True for existing path."""
        ns = ContextNamespace("db", {"customer": {"id": "123"}})
        assert ns.has("customer.id") is True

    def test_has_missing_path(self):
        """Test has returns False for missing path."""
        ns = ContextNamespace("db", {"customer": {"id": "123"}})
        assert ns.has("customer.missing") is False

    def test_merge_adds_new_keys(self):
        """Test merge adds new keys."""
        ns = ContextNamespace("db", {"a": 1})
        ns.merge({"b": 2})
        assert ns.get("a") == 1
        assert ns.get("b") == 2

    def test_merge_deep_merges_dicts(self):
        """Test merge deep merges nested dicts."""
        ns = ContextNamespace("db", {"customer": {"id": "123"}})
        ns.merge({"customer": {"name": "John"}})
        assert ns.get("customer.id") == "123"
        assert ns.get("customer.name") == "John"


class TestRuntimeContext:
    """Tests for RuntimeContext."""

    def test_init_empty(self):
        """Test initializing empty context."""
        ctx = RuntimeContext()
        assert ctx.to_dict() == {"db": {}, "state": {}, "input": {}, "logic": {}}

    def test_init_with_data(self, sample_context_data):
        """Test initializing with data."""
        ctx = RuntimeContext(sample_context_data)
        assert ctx.db.get("customer.id") == "CUST-123"

    def test_get_with_namespace(self, runtime_context):
        """Test get with full path including namespace."""
        assert runtime_context.get("db.customer.id") == "CUST-123"
        assert runtime_context.get("state.case_id") == "CASE-789"
        assert runtime_context.get("input.dispute_reason") == "Incorrect charge"

    def test_get_invalid_namespace_raises(self, runtime_context):
        """Test that invalid namespace raises error."""
        with pytest.raises(ContextPathError) as exc_info:
            runtime_context.get("invalid.path")
        assert "Unknown namespace" in str(exc_info.value)

    def test_get_invalid_format_raises(self, runtime_context):
        """Test that invalid path format raises error."""
        with pytest.raises(ContextPathError) as exc_info:
            runtime_context.get("nonamespace")
        assert "Invalid path format" in str(exc_info.value)

    def test_set_with_namespace(self):
        """Test set with full path including namespace."""
        ctx = RuntimeContext()
        ctx.set("logic.credit_amount", 150.00)
        assert ctx.get("logic.credit_amount") == 150.00

    def test_set_in_db_namespace(self):
        """Test setting in db namespace."""
        ctx = RuntimeContext()
        ctx.set("db.customer.id", "CUST-999")
        assert ctx.get("db.customer.id") == "CUST-999"

    def test_has_existing(self, runtime_context):
        """Test has returns True for existing path."""
        assert runtime_context.has("db.customer.id") is True

    def test_has_missing(self, runtime_context):
        """Test has returns False for missing path."""
        assert runtime_context.has("db.customer.missing") is False

    def test_merge_namespaces(self):
        """Test merging data into namespaces."""
        ctx = RuntimeContext()
        ctx.merge({
            "db": {"customer": {"id": "123"}},
            "state": {"case_id": "456"},
        })
        assert ctx.get("db.customer.id") == "123"
        assert ctx.get("state.case_id") == "456"

    def test_to_dict(self, runtime_context):
        """Test to_dict returns all namespaces."""
        result = runtime_context.to_dict()
        assert "db" in result
        assert "state" in result
        assert "input" in result
        assert "logic" in result
        assert result["db"]["customer"]["id"] == "CUST-123"

    def test_to_flat_dict(self, runtime_context):
        """Test to_flat_dict returns flattened keys."""
        result = runtime_context.to_flat_dict()
        assert "db.customer.id" in result
        assert result["db.customer.id"] == "CUST-123"
        assert "state.case_id" in result
        assert result["state.case_id"] == "CASE-789"

    def test_update_from_response(self):
        """Test update_from_response stores in state."""
        ctx = RuntimeContext()
        ctx.update_from_response({"adjustmentId": "ADJ-123", "amount": 50})
        assert ctx.get("state.last_response.adjustmentId") == "ADJ-123"
        assert ctx.get("state.last_response.amount") == 50

    def test_set_logic_values(self):
        """Test set_logic_values sets multiple values."""
        ctx = RuntimeContext()
        ctx.set_logic_values({
            "credit_amount": 100,
            "escalation_required": False,
        })
        assert ctx.get("logic.credit_amount") == 100
        assert ctx.get("logic.escalation_required") is False

    def test_set_logic_values_with_prefix(self):
        """Test set_logic_values handles both formats."""
        ctx = RuntimeContext()
        ctx.set_logic_values({
            "logic.with_prefix": "value1",
            "without_prefix": "value2",
        })
        assert ctx.get("logic.with_prefix") == "value1"
        assert ctx.get("logic.without_prefix") == "value2"

    def test_namespace_isolation(self):
        """Test that namespaces are isolated."""
        ctx = RuntimeContext()
        ctx.set("db.value", "db_value")
        ctx.set("state.value", "state_value")
        assert ctx.get("db.value") == "db_value"
        assert ctx.get("state.value") == "state_value"
        assert ctx.get("db.value") != ctx.get("state.value")
