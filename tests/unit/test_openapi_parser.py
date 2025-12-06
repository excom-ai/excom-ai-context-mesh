"""Unit tests for OpenAPIParser."""

from pathlib import Path

import pytest
import yaml

from contextmesh.parsers.openapi_parser import (
    OpenAPIParser,
    OpenAPISpec,
    load_spec,
    load_specs_from_directory,
)
from contextmesh.utils.exceptions import OpenAPIParseError


class TestOpenAPIParser:
    """Tests for OpenAPIParser."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return OpenAPIParser()

    def test_parse_spec_extracts_info(self, parser, sample_openapi_yaml):
        """Test that info section is extracted."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)
        assert spec.title == "Test API"
        assert spec.version == "1.0.0"

    def test_parse_spec_extracts_servers(self, parser, sample_openapi_yaml):
        """Test that servers are extracted."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)
        assert len(spec.servers) == 1
        assert spec.servers[0]["url"] == "https://api.test.com/v1"

    def test_parse_spec_extracts_endpoints(self, parser, sample_openapi_yaml):
        """Test that endpoints are extracted."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)
        assert len(spec.endpoints) == 2

    def test_parse_endpoint_operation_id(self, parser, sample_openapi_yaml):
        """Test that operation ID is extracted."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)
        operation_ids = [ep.operation_id for ep in spec.endpoints]
        assert "createItem" in operation_ids
        assert "getItem" in operation_ids

    def test_parse_endpoint_method_and_path(self, parser, sample_openapi_yaml):
        """Test that method and path are extracted."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)
        create_endpoint = spec.get_endpoint("createItem")
        assert create_endpoint.method == "POST"
        assert create_endpoint.path == "/items"

    def test_parse_contextmesh_extension(self, parser, sample_openapi_yaml):
        """Test that x-contextMesh extension is parsed."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)
        create_endpoint = spec.get_endpoint("createItem")

        assert create_endpoint.contextmesh is not None
        assert create_endpoint.contextmesh.logic_module == "test_module"
        assert "name" in create_endpoint.contextmesh.template_params

    def test_parse_template_params(self, parser, sample_openapi_yaml):
        """Test that template params are extracted."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)
        create_endpoint = spec.get_endpoint("createItem")

        params = create_endpoint.contextmesh.template_params
        assert params["name"] == "{{input.item_name}}"
        assert params["value"] == "{{logic.calculated_value}}"

    def test_parse_state_updates(self, parser, sample_openapi_yaml):
        """Test that state updates are extracted."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)
        create_endpoint = spec.get_endpoint("createItem")

        state_updates = create_endpoint.contextmesh.state_updates
        assert "onSuccess" in state_updates
        assert len(state_updates["onSuccess"]) == 1

    def test_endpoint_without_contextmesh(self, parser, sample_openapi_yaml):
        """Test endpoint without x-contextMesh extension."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)
        get_endpoint = spec.get_endpoint("getItem")

        # getItem doesn't have x-contextMesh in the sample
        assert get_endpoint.contextmesh is None

    def test_get_endpoint_by_id(self, parser, sample_openapi_yaml):
        """Test getting endpoint by operation ID."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)

        endpoint = spec.get_endpoint("createItem")
        assert endpoint is not None
        assert endpoint.operation_id == "createItem"

        missing = spec.get_endpoint("nonexistent")
        assert missing is None

    def test_get_endpoints_by_logic_module(self, parser, sample_openapi_yaml):
        """Test getting endpoints by logic module."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)

        endpoints = spec.get_endpoints_by_logic_module("test_module")
        assert len(endpoints) == 1
        assert endpoints[0].operation_id == "createItem"

    def test_get_base_url(self, parser, sample_openapi_yaml):
        """Test getting base URL from spec."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)

        assert spec.get_base_url() == "https://api.test.com/v1"

    def test_load_spec_from_file(self, parser, fixtures_dir):
        """Test loading spec from YAML file."""
        spec_path = fixtures_dir / "test_openapi.yaml"
        spec = parser.load_spec(spec_path)

        assert spec.title == "Test Billing API"
        assert len(spec.endpoints) >= 2

    def test_load_spec_file_not_found(self, parser):
        """Test that missing file raises error."""
        with pytest.raises(OpenAPIParseError) as exc_info:
            parser.load_spec("/nonexistent/spec.yaml")
        assert "not found" in str(exc_info.value)

    def test_convenience_load_spec(self, fixtures_dir):
        """Test the load_spec convenience function."""
        spec_path = fixtures_dir / "test_openapi.yaml"
        spec = load_spec(spec_path)
        assert isinstance(spec, OpenAPISpec)

    def test_load_specs_from_directory(self, fixtures_dir):
        """Test loading multiple specs from directory."""
        specs = load_specs_from_directory(fixtures_dir)
        assert len(specs) >= 1

    def test_parse_request_schema(self, parser, sample_openapi_yaml):
        """Test that request schema is parsed."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)
        create_endpoint = spec.get_endpoint("createItem")

        assert create_endpoint.request_schema is not None
        assert "properties" in create_endpoint.request_schema

    def test_parse_response_schema(self, parser, sample_openapi_yaml):
        """Test that response schema is parsed."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)
        create_endpoint = spec.get_endpoint("createItem")

        assert create_endpoint.response_schema is not None

    def test_parse_path_parameters(self, parser, sample_openapi_yaml):
        """Test that path parameters are parsed."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)
        get_endpoint = spec.get_endpoint("getItem")

        assert get_endpoint.path == "/items/{itemId}"
        assert get_endpoint.request_schema is not None

    def test_raw_spec_preserved(self, parser, sample_openapi_yaml):
        """Test that raw spec is preserved."""
        spec_dict = yaml.safe_load(sample_openapi_yaml)
        spec = parser.parse_spec(spec_dict)

        assert spec.raw_spec == spec_dict


class TestOpenAPISpec:
    """Tests for OpenAPISpec class."""

    def test_get_endpoint_returns_none_for_missing(self):
        """Test get_endpoint returns None for missing ID."""
        spec = OpenAPISpec(
            title="Test",
            version="1.0",
            servers=[],
            endpoints=[],
            raw_spec={},
        )
        assert spec.get_endpoint("missing") is None

    def test_get_base_url_empty_servers(self):
        """Test get_base_url with no servers."""
        spec = OpenAPISpec(
            title="Test",
            version="1.0",
            servers=[],
            endpoints=[],
            raw_spec={},
        )
        assert spec.get_base_url() == ""
