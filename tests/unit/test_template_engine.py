"""Unit tests for TemplateEngine."""

import pytest

from contextmesh.core.context import RuntimeContext
from contextmesh.templating.engine import TemplateEngine, resolve_template
from contextmesh.utils.exceptions import TemplateResolutionError


class TestTemplateEngine:
    """Tests for TemplateEngine."""

    @pytest.fixture
    def engine(self):
        """Create a template engine instance."""
        return TemplateEngine()

    def test_resolve_simple_template(self, engine, runtime_context):
        """Test resolving a simple template."""
        result = engine.resolve("{{db.customer.id}}", runtime_context)
        assert result == "CUST-123"

    def test_resolve_preserves_type_for_single_expression(self, engine, runtime_context):
        """Test that single expression preserves type."""
        result = engine.resolve("{{db.customer.arpu}}", runtime_context)
        assert result == 85.50
        assert isinstance(result, float)

    def test_resolve_string_interpolation(self, engine, runtime_context):
        """Test resolving template with text around expression."""
        result = engine.resolve(
            "Customer {{db.customer.id}} has case {{state.case_id}}",
            runtime_context
        )
        assert result == "Customer CUST-123 has case CASE-789"

    def test_resolve_multiple_expressions(self, engine, runtime_context):
        """Test resolving template with multiple expressions."""
        result = engine.resolve(
            "{{db.customer.name}} - {{db.invoice.number}}",
            runtime_context
        )
        assert result == "John Smith - INV-456"

    def test_resolve_nested_path(self, engine, runtime_context):
        """Test resolving deeply nested path."""
        result = engine.resolve("{{db.customer.tenure_months}}", runtime_context)
        assert result == 24

    def test_resolve_missing_path_raises(self, engine, runtime_context):
        """Test that missing path raises error."""
        with pytest.raises(TemplateResolutionError):
            engine.resolve("{{db.customer.nonexistent}}", runtime_context)

    def test_resolve_invalid_namespace_raises(self, engine, runtime_context):
        """Test that invalid namespace raises error."""
        with pytest.raises(TemplateResolutionError):
            engine.resolve("{{invalid.path}}", runtime_context)

    def test_resolve_dict_simple(self, engine, runtime_context):
        """Test resolving a dictionary of templates."""
        template_dict = {
            "customerId": "{{db.customer.customer_id}}",
            "caseId": "{{state.case_id}}",
        }
        result = engine.resolve_dict(template_dict, runtime_context)
        assert result["customerId"] == "CUST-123"
        assert result["caseId"] == "CASE-789"

    def test_resolve_dict_nested(self, engine, runtime_context):
        """Test resolving nested dictionary."""
        template_dict = {
            "customer": {
                "id": "{{db.customer.customer_id}}",
                "name": "{{db.customer.name}}",
            }
        }
        result = engine.resolve_dict(template_dict, runtime_context)
        assert result["customer"]["id"] == "CUST-123"
        assert result["customer"]["name"] == "John Smith"

    def test_resolve_dict_mixed_values(self, engine, runtime_context):
        """Test resolving dict with non-template values."""
        template_dict = {
            "customerId": "{{db.customer.customer_id}}",
            "static": "literal value",
            "number": 42,
        }
        result = engine.resolve_dict(template_dict, runtime_context)
        assert result["customerId"] == "CUST-123"
        assert result["static"] == "literal value"
        assert result["number"] == 42

    def test_resolve_params_strict_mode(self, engine, runtime_context):
        """Test resolve_params in strict mode."""
        template_params = {
            "customerId": "{{db.customer.customer_id}}",
            "missing": "{{db.nonexistent}}",
        }
        with pytest.raises(TemplateResolutionError):
            engine.resolve_params(template_params, runtime_context, strict=True)

    def test_resolve_params_non_strict_mode(self, engine, runtime_context):
        """Test resolve_params skips missing in non-strict mode."""
        template_params = {
            "customerId": "{{db.customer.customer_id}}",
            "missing": "{{db.nonexistent}}",
        }
        result = engine.resolve_params(template_params, runtime_context, strict=False)
        assert result["customerId"] == "CUST-123"
        assert "missing" not in result

    def test_validate_template_valid(self, engine):
        """Test validating a valid template."""
        assert engine.validate_template("{{db.customer.id}}") is True
        assert engine.validate_template("Hello {{db.name}}!") is True

    def test_validate_template_invalid_braces(self, engine):
        """Test validating template with unbalanced braces."""
        assert engine.validate_template("{{db.customer.id}") is False
        assert engine.validate_template("{db.customer.id}}") is False

    def test_validate_template_invalid_path(self, engine):
        """Test validating template with invalid path."""
        assert engine.validate_template("{{invalid}}") is False
        assert engine.validate_template("{{no_namespace}}") is False

    def test_extract_paths(self, engine):
        """Test extracting paths from template."""
        template = "Customer {{db.customer.id}} case {{state.case_id}}"
        paths = engine.extract_paths(template)
        assert "db.customer.id" in paths
        assert "state.case_id" in paths

    def test_extract_paths_empty(self, engine):
        """Test extracting paths from template without expressions."""
        paths = engine.extract_paths("No templates here")
        assert paths == []

    def test_resolve_response_path(self, engine):
        """Test resolving response.* paths."""
        ctx = RuntimeContext()
        ctx.update_from_response({"adjustmentId": "ADJ-123"})

        result = engine.resolve("{{response.adjustmentId}}", ctx)
        assert result == "ADJ-123"

    def test_resolve_response_path_missing_raises(self, engine):
        """Test that missing response path raises error."""
        ctx = RuntimeContext()
        with pytest.raises(TemplateResolutionError) as exc_info:
            engine.resolve("{{response.missing}}", ctx)
        assert "Response path not found" in str(exc_info.value)

    def test_resolve_whitespace_handling(self, engine, runtime_context):
        """Test that whitespace in templates is handled."""
        result = engine.resolve("{{ db.customer.id }}", runtime_context)
        assert result == "CUST-123"

    def test_convenience_function(self, runtime_context):
        """Test the resolve_template convenience function."""
        result = resolve_template("{{db.customer.id}}", runtime_context)
        assert result == "CUST-123"

    def test_resolve_logic_namespace(self, engine):
        """Test resolving from logic namespace."""
        ctx = RuntimeContext()
        ctx.set("logic.credit_amount", 150.00)
        ctx.set("logic.escalation_required", False)

        assert engine.resolve("{{logic.credit_amount}}", ctx) == 150.00
        assert engine.resolve("{{logic.escalation_required}}", ctx) is False

    def test_resolve_input_namespace(self, engine, runtime_context):
        """Test resolving from input namespace."""
        result = engine.resolve("{{input.dispute_reason}}", runtime_context)
        assert result == "Incorrect charge"

    def test_resolve_all_namespaces(self, engine, runtime_context):
        """Test resolving from all namespaces in one template."""
        runtime_context.set("logic.status", "approved")

        template = "{{db.customer.id}} {{state.case_id}} {{input.dispute_reason}} {{logic.status}}"
        result = engine.resolve(template, runtime_context)

        assert "CUST-123" in result
        assert "CASE-789" in result
        assert "Incorrect charge" in result
        assert "approved" in result
