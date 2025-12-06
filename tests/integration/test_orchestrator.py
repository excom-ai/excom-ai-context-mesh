"""Integration tests for ContextMeshOrchestrator."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from contextmesh.core.context import RuntimeContext
from contextmesh.core.models import (
    ContextMeshConfig,
    ContextMeshExtension,
    OpenAPIEndpoint,
    Playbook,
    PlaybookVariable,
    WorkflowPlan,
    WorkflowStep,
)
from contextmesh.core.orchestrator import ContextMeshOrchestrator
from contextmesh.execution.api_executor import MockAPIExecutor
from contextmesh.parsers.openapi_parser import OpenAPISpec


class TestOrchestratorSetup:
    """Tests for orchestrator initialization."""

    @pytest.fixture
    def fixtures_dir(self):
        """Return fixtures directory."""
        return Path(__file__).parent.parent / "fixtures"

    @pytest.fixture
    def config(self, fixtures_dir):
        """Create a test config."""
        return ContextMeshConfig(
            anthropic_api_key="test-key",
            openapi_specs_dir=str(fixtures_dir),
            playbooks_dir=str(fixtures_dir),
        )

    def test_init_loads_playbooks(self, config):
        """Test that playbooks are loaded on init."""
        orchestrator = ContextMeshOrchestrator(config)
        playbooks = orchestrator.list_playbooks()
        assert "test_playbook" in playbooks or "test_billing_resolution" in playbooks

    def test_init_loads_specs(self, config):
        """Test that specs are loaded on init."""
        orchestrator = ContextMeshOrchestrator(config)
        endpoints = orchestrator.list_endpoints()
        assert len(endpoints) > 0

    def test_init_with_empty_directories(self, tmp_path):
        """Test init with empty directories."""
        config = ContextMeshConfig(
            anthropic_api_key="test-key",
            openapi_specs_dir=str(tmp_path / "specs"),
            playbooks_dir=str(tmp_path / "playbooks"),
        )
        # Should not raise, just have empty resources
        orchestrator = ContextMeshOrchestrator(config)
        assert orchestrator.list_playbooks() == []

    def test_add_playbook(self, config, sample_playbook):
        """Test adding a playbook programmatically."""
        orchestrator = ContextMeshOrchestrator(config)
        orchestrator.add_playbook(sample_playbook)
        assert sample_playbook.module_name in orchestrator.list_playbooks()

    def test_add_spec(self, config, sample_endpoint):
        """Test adding a spec programmatically."""
        orchestrator = ContextMeshOrchestrator(config)
        spec = OpenAPISpec(
            title="Test Spec",
            version="1.0.0",
            servers=[{"url": "https://api.test.com"}],
            endpoints=[sample_endpoint],
            raw_spec={},
        )
        orchestrator.add_spec(spec)
        assert sample_endpoint.operation_id in orchestrator.list_endpoints()


class TestOrchestratorPlanning:
    """Tests for workflow planning (without actual LLM calls)."""

    @pytest.fixture
    def mock_planner(self):
        """Create a mock planner."""
        planner = MagicMock()
        planner.plan_workflow.return_value = WorkflowPlan(
            steps=[
                WorkflowStep(
                    order=1,
                    operation_id="createBillingAdjustment",
                    description="Create billing adjustment",
                ),
                WorkflowStep(
                    order=2,
                    operation_id="sendNotification",
                    description="Send notification",
                ),
            ],
            logic_values={
                "recommended_credit_amount": 75.00,
                "escalation_required": False,
                "resolution_type": "full_credit",
            },
            reasoning="High churn risk customer with small dispute amount",
        )
        planner.compute_logic_values.return_value = {
            "recommended_credit_amount": 75.00,
            "escalation_required": False,
        }
        return planner

    @pytest.fixture
    def orchestrator_with_mock(self, fixtures_dir, mock_planner):
        """Create orchestrator with mocked planner."""
        config = ContextMeshConfig(
            anthropic_api_key="test-key",
            openapi_specs_dir=str(fixtures_dir),
            playbooks_dir=str(fixtures_dir),
        )
        orchestrator = ContextMeshOrchestrator(config)
        orchestrator.planner = mock_planner
        return orchestrator

    @pytest.fixture
    def fixtures_dir(self):
        """Return fixtures directory."""
        return Path(__file__).parent.parent / "fixtures"

    def test_plan_only(self, orchestrator_with_mock, sample_context_data):
        """Test generating a plan without execution."""
        plan = orchestrator_with_mock.plan_only(
            trigger="test_billing_resolution",
            initial_context=sample_context_data,
        )

        assert plan is not None
        assert len(plan.steps) == 2
        assert plan.logic_values["recommended_credit_amount"] == 75.00

    def test_compute_logic_values(self, orchestrator_with_mock, sample_context_data):
        """Test computing logic values only."""
        values = orchestrator_with_mock.compute_logic_values(
            trigger="test_billing_resolution",
            initial_context=sample_context_data,
        )

        assert "recommended_credit_amount" in values
        assert values["recommended_credit_amount"] == 75.00


class TestOrchestratorExecution:
    """Tests for workflow execution (with mocked API calls)."""

    @pytest.fixture
    def fixtures_dir(self):
        """Return fixtures directory."""
        return Path(__file__).parent.parent / "fixtures"

    @pytest.fixture
    def mock_responses(self):
        """Mock API responses."""
        return {
            "createBillingAdjustment": {
                "adjustmentId": "ADJ-123",
                "amount": 75.00,
                "createdAt": "2024-01-15T10:00:00Z",
            },
            "sendNotification": {
                "notificationId": "NOT-456",
                "status": "sent",
            },
        }

    @pytest.fixture
    def mock_planner(self):
        """Create a mock planner."""
        planner = MagicMock()
        planner.plan_workflow.return_value = WorkflowPlan(
            steps=[
                WorkflowStep(
                    order=1,
                    operation_id="createBillingAdjustment",
                    description="Create billing adjustment",
                ),
            ],
            logic_values={
                "recommended_credit_amount": 75.00,
                "resolution_type": "full_credit",
            },
            reasoning="Test reasoning",
        )
        return planner

    def test_execute_workflow_success(
        self, fixtures_dir, mock_planner, mock_responses, sample_context_data
    ):
        """Test successful workflow execution."""
        config = ContextMeshConfig(
            anthropic_api_key="test-key",
            openapi_specs_dir=str(fixtures_dir),
            playbooks_dir=str(fixtures_dir),
        )
        orchestrator = ContextMeshOrchestrator(config)
        orchestrator.planner = mock_planner

        # Mock the API executor
        with patch.object(
            orchestrator, "_get_base_url", return_value="https://api.test.com"
        ):
            with patch(
                "contextmesh.core.orchestrator.APIExecutor"
            ) as MockExecutor:
                mock_executor = MockAPIExecutor(mock_responses)
                MockExecutor.return_value = mock_executor

                result = orchestrator.execute_workflow(
                    trigger="test_billing_resolution",
                    initial_context=sample_context_data,
                )

        # Should have attempted to execute
        assert result is not None
        assert result.plan is not None

    def test_execute_workflow_missing_playbook(self, fixtures_dir, sample_context_data):
        """Test error when playbook not found."""
        config = ContextMeshConfig(
            anthropic_api_key="test-key",
            openapi_specs_dir=str(fixtures_dir),
            playbooks_dir=str(fixtures_dir),
        )
        orchestrator = ContextMeshOrchestrator(config)

        result = orchestrator.execute_workflow(
            trigger="nonexistent_playbook",
            initial_context=sample_context_data,
        )

        assert result.success is False
        assert any("not found" in err.lower() for err in result.errors)

    def test_workflow_result_contains_final_context(
        self, fixtures_dir, mock_planner, mock_responses, sample_context_data
    ):
        """Test that result contains final context state."""
        config = ContextMeshConfig(
            anthropic_api_key="test-key",
            openapi_specs_dir=str(fixtures_dir),
            playbooks_dir=str(fixtures_dir),
        )
        orchestrator = ContextMeshOrchestrator(config)
        orchestrator.planner = mock_planner

        with patch.object(
            orchestrator, "_get_base_url", return_value="https://api.test.com"
        ):
            with patch(
                "contextmesh.core.orchestrator.APIExecutor"
            ) as MockExecutor:
                mock_executor = MockAPIExecutor(mock_responses)
                MockExecutor.return_value = mock_executor

                result = orchestrator.execute_workflow(
                    trigger="test_billing_resolution",
                    initial_context=sample_context_data,
                )

        assert "db" in result.final_context
        assert "logic" in result.final_context


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)
class TestOrchestratorWithRealLLM:
    """Integration tests that use real LLM calls.

    These tests require ANTHROPIC_API_KEY to be set.
    """

    @pytest.fixture
    def fixtures_dir(self):
        """Return fixtures directory."""
        return Path(__file__).parent.parent / "fixtures"

    @pytest.fixture
    def real_config(self, fixtures_dir):
        """Create config with real API key."""
        return ContextMeshConfig(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            openapi_specs_dir=str(fixtures_dir),
            playbooks_dir=str(fixtures_dir),
            model="claude-haiku-4-5-20251001",
        )

    def test_real_plan_generation(self, real_config, sample_context_data):
        """Test generating a real plan with LLM."""
        orchestrator = ContextMeshOrchestrator(real_config)

        plan = orchestrator.plan_only(
            trigger="test_billing_resolution",
            initial_context=sample_context_data,
        )

        assert plan is not None
        assert len(plan.steps) > 0
        assert plan.reasoning != ""

    def test_real_logic_computation(self, real_config, sample_context_data):
        """Test computing logic values with real LLM."""
        orchestrator = ContextMeshOrchestrator(real_config)

        values = orchestrator.compute_logic_values(
            trigger="test_billing_resolution",
            initial_context=sample_context_data,
        )

        # Should compute at least some logic values
        assert isinstance(values, dict)
