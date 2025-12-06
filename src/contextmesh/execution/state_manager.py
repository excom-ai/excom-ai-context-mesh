"""State management for workflow execution."""

from abc import ABC, abstractmethod
from typing import Any

from contextmesh.core.context import RuntimeContext
from contextmesh.core.models import APIResponse, StateUpdate
from contextmesh.templating.engine import TemplateEngine


class StateBackend(ABC):
    """Abstract base class for state persistence backends."""

    @abstractmethod
    def write(self, update: StateUpdate) -> bool:
        """Write data to the state store.

        Args:
            update: StateUpdate describing the write operation

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def read(self, table: str, query: dict[str, Any]) -> dict[str, Any] | None:
        """Read data from the state store.

        Args:
            table: Table/collection name
            query: Query conditions

        Returns:
            Matching data or None
        """
        pass

    @abstractmethod
    def update(self, update: StateUpdate) -> bool:
        """Update existing data.

        Args:
            update: StateUpdate with condition and values

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def delete(self, table: str, condition: dict[str, Any]) -> bool:
        """Delete data from state store.

        Args:
            table: Table/collection name
            condition: Delete condition

        Returns:
            True if successful
        """
        pass


class InMemoryStateBackend(StateBackend):
    """In-memory state backend for testing and simple use cases."""

    def __init__(self):
        self._data: dict[str, list[dict[str, Any]]] = {}

    def write(self, update: StateUpdate) -> bool:
        """Write data to in-memory store."""
        if update.table not in self._data:
            self._data[update.table] = []

        self._data[update.table].append(update.values.copy())
        return True

    def read(self, table: str, query: dict[str, Any]) -> dict[str, Any] | None:
        """Read first matching record."""
        if table not in self._data:
            return None

        for record in self._data[table]:
            if self._matches(record, query):
                return record

        return None

    def read_all(self, table: str, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Read all matching records."""
        if table not in self._data:
            return []

        if query is None:
            return self._data[table].copy()

        return [r for r in self._data[table] if self._matches(r, query)]

    def update(self, update: StateUpdate) -> bool:
        """Update matching records."""
        if update.table not in self._data:
            return False

        updated = False
        for record in self._data[update.table]:
            if update.condition and self._matches(record, update.condition):
                record.update(update.values)
                updated = True

        return updated

    def delete(self, table: str, condition: dict[str, Any]) -> bool:
        """Delete matching records."""
        if table not in self._data:
            return False

        original_len = len(self._data[table])
        self._data[table] = [
            r for r in self._data[table] if not self._matches(r, condition)
        ]

        return len(self._data[table]) < original_len

    def clear(self, table: str | None = None) -> None:
        """Clear data from store.

        Args:
            table: Specific table to clear, or None for all
        """
        if table:
            self._data.pop(table, None)
        else:
            self._data.clear()

    def _matches(self, record: dict[str, Any], query: dict[str, Any]) -> bool:
        """Check if a record matches a query."""
        for key, value in query.items():
            if key not in record or record[key] != value:
                return False
        return True


class StateManager:
    """Manages state updates during workflow execution."""

    def __init__(self, backend: StateBackend | None = None):
        """Initialize state manager.

        Args:
            backend: State backend to use (defaults to InMemoryStateBackend)
        """
        self.backend = backend or InMemoryStateBackend()
        self.template_engine = TemplateEngine()
        self.update_history: list[StateUpdate] = []

    def apply_updates(
        self,
        state_updates: dict[str, Any],
        context: RuntimeContext,
        response: APIResponse,
    ) -> list[StateUpdate]:
        """Apply state updates based on API response.

        Args:
            state_updates: x-contextMesh.stateUpdates configuration
            context: Current runtime context
            response: API response to use for templates

        Returns:
            List of applied StateUpdate objects
        """
        applied: list[StateUpdate] = []

        # Update context with response for template resolution
        context.update_from_response(response.body)

        # Determine which updates to apply based on success/failure
        updates_to_apply = []

        if response.success and "onSuccess" in state_updates:
            updates_to_apply.extend(state_updates["onSuccess"])
        elif not response.success and "onFailure" in state_updates:
            updates_to_apply.extend(state_updates["onFailure"])

        # Also apply any "always" updates
        if "always" in state_updates:
            updates_to_apply.extend(state_updates["always"])

        # Process each update
        for update_config in updates_to_apply:
            state_update = self._process_update(update_config, context)
            if state_update:
                self._execute_update(state_update)
                applied.append(state_update)
                self.update_history.append(state_update)

        return applied

    def _process_update(
        self,
        update_config: dict[str, Any],
        context: RuntimeContext,
    ) -> StateUpdate | None:
        """Process a single update configuration.

        Args:
            update_config: Update configuration from spec
            context: Runtime context for template resolution

        Returns:
            StateUpdate object or None
        """
        # Determine operation type
        if "write" in update_config:
            return self._create_write_update(update_config["write"], context)
        elif "update" in update_config:
            return self._create_update_update(update_config["update"], context)
        elif "delete" in update_config:
            return self._create_delete_update(update_config["delete"], context)

        return None

    def _create_write_update(
        self,
        config: dict[str, Any],
        context: RuntimeContext,
    ) -> StateUpdate:
        """Create a write StateUpdate."""
        table = config.get("table", "")
        values = self._resolve_values(config.get("values", {}), context)

        return StateUpdate(
            operation="write",
            table=table,
            values=values,
        )

    def _create_update_update(
        self,
        config: dict[str, Any],
        context: RuntimeContext,
    ) -> StateUpdate:
        """Create an update StateUpdate."""
        table = config.get("table", "")
        values = self._resolve_values(config.get("values", {}), context)
        condition = self._resolve_values(config.get("condition", {}), context)

        return StateUpdate(
            operation="update",
            table=table,
            values=values,
            condition=condition,
        )

    def _create_delete_update(
        self,
        config: dict[str, Any],
        context: RuntimeContext,
    ) -> StateUpdate:
        """Create a delete StateUpdate."""
        table = config.get("table", "")
        condition = self._resolve_values(config.get("condition", {}), context)

        return StateUpdate(
            operation="delete",
            table=table,
            values={},
            condition=condition,
        )

    def _resolve_values(
        self,
        values: dict[str, Any],
        context: RuntimeContext,
    ) -> dict[str, Any]:
        """Resolve template values in a dictionary."""
        resolved: dict[str, Any] = {}

        for key, value in values.items():
            if isinstance(value, str) and "{{" in value:
                try:
                    resolved[key] = self.template_engine.resolve(value, context)
                except Exception:
                    resolved[key] = value  # Keep original if resolution fails
            else:
                resolved[key] = value

        return resolved

    def _execute_update(self, update: StateUpdate) -> bool:
        """Execute a state update against the backend."""
        if update.operation == "write":
            return self.backend.write(update)
        elif update.operation == "update":
            return self.backend.update(update)
        elif update.operation == "delete":
            return self.backend.delete(update.table, update.condition or {})
        return False

    def get_history(self) -> list[StateUpdate]:
        """Get the history of applied updates."""
        return self.update_history.copy()

    def clear_history(self) -> None:
        """Clear the update history."""
        self.update_history.clear()
