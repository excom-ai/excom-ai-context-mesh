"""Runtime context management for ContextMesh."""

from typing import Any

from contextmesh.utils.exceptions import ContextPathError


class ContextNamespace:
    """A namespace within the runtime context (db, state, input, logic)."""

    def __init__(self, name: str, data: dict[str, Any] | None = None):
        self._name = name
        self._data: dict[str, Any] = data or {}

    def get(self, path: str) -> Any:
        """Get a value by dot-notation path.

        Args:
            path: Dot-separated path (e.g., 'customer.id')

        Returns:
            The value at the path

        Raises:
            ContextPathError: If path doesn't exist
        """
        parts = path.split(".")
        current = self._data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                raise ContextPathError(f"Path '{self._name}.{path}' not found in context")

        return current

    def set(self, path: str, value: Any) -> None:
        """Set a value at a dot-notation path.

        Args:
            path: Dot-separated path (e.g., 'customer.id')
            value: Value to set
        """
        parts = path.split(".")
        current = self._data

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value

    def has(self, path: str) -> bool:
        """Check if a path exists."""
        try:
            self.get(path)
            return True
        except ContextPathError:
            return False

    def to_dict(self) -> dict[str, Any]:
        """Return the namespace data as a dictionary."""
        return self._data.copy()

    def merge(self, data: dict[str, Any]) -> None:
        """Merge data into the namespace."""
        self._deep_merge(self._data, data)

    def _deep_merge(self, target: dict, source: dict) -> None:
        """Deep merge source into target."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value


class RuntimeContext:
    """Main context object holding all namespaces (db, state, input, logic)."""

    def __init__(self, initial_data: dict[str, Any] | None = None):
        """Initialize runtime context.

        Args:
            initial_data: Optional dict with keys 'db', 'state', 'input', 'logic'
        """
        initial_data = initial_data or {}

        self.db = ContextNamespace("db", initial_data.get("db", {}))
        self.state = ContextNamespace("state", initial_data.get("state", {}))
        self.input = ContextNamespace("input", initial_data.get("input", {}))
        self.logic = ContextNamespace("logic", initial_data.get("logic", {}))

        self._namespaces = {
            "db": self.db,
            "state": self.state,
            "input": self.input,
            "logic": self.logic,
        }

    def get(self, path: str) -> Any:
        """Get a value by full dot-notation path.

        Args:
            path: Full path including namespace (e.g., 'db.customer.id')

        Returns:
            The value at the path

        Raises:
            ContextPathError: If namespace invalid or path doesn't exist
        """
        parts = path.split(".", 1)

        if len(parts) < 2:
            raise ContextPathError(f"Invalid path format: '{path}'. Expected 'namespace.path'")

        namespace_name, remaining_path = parts

        if namespace_name not in self._namespaces:
            raise ContextPathError(
                f"Unknown namespace: '{namespace_name}'. "
                f"Valid namespaces: {list(self._namespaces.keys())}"
            )

        return self._namespaces[namespace_name].get(remaining_path)

    def set(self, path: str, value: Any) -> None:
        """Set a value at a full dot-notation path.

        Args:
            path: Full path including namespace (e.g., 'logic.credit_amount')
            value: Value to set
        """
        parts = path.split(".", 1)

        if len(parts) < 2:
            raise ContextPathError(f"Invalid path format: '{path}'. Expected 'namespace.path'")

        namespace_name, remaining_path = parts

        if namespace_name not in self._namespaces:
            raise ContextPathError(
                f"Unknown namespace: '{namespace_name}'. "
                f"Valid namespaces: {list(self._namespaces.keys())}"
            )

        self._namespaces[namespace_name].set(remaining_path, value)

    def has(self, path: str) -> bool:
        """Check if a full path exists."""
        try:
            self.get(path)
            return True
        except ContextPathError:
            return False

    def merge(self, data: dict[str, Any]) -> None:
        """Merge data into context namespaces.

        Args:
            data: Dict with optional keys 'db', 'state', 'input', 'logic'
        """
        for namespace_name, namespace_data in data.items():
            if namespace_name in self._namespaces and isinstance(namespace_data, dict):
                self._namespaces[namespace_name].merge(namespace_data)

    def to_dict(self) -> dict[str, Any]:
        """Return the entire context as a dictionary."""
        return {
            "db": self.db.to_dict(),
            "state": self.state.to_dict(),
            "input": self.input.to_dict(),
            "logic": self.logic.to_dict(),
        }

    def to_flat_dict(self) -> dict[str, Any]:
        """Return context as a flat dictionary with dot-notation keys.

        Useful for template resolution.
        """
        result = {}
        for namespace_name, namespace in self._namespaces.items():
            self._flatten(namespace.to_dict(), namespace_name, result)
        return result

    def _flatten(
        self, data: dict[str, Any], prefix: str, result: dict[str, Any]
    ) -> None:
        """Recursively flatten a nested dict."""
        for key, value in data.items():
            full_key = f"{prefix}.{key}"
            if isinstance(value, dict):
                self._flatten(value, full_key, result)
            else:
                result[full_key] = value

    def update_from_response(self, response: dict[str, Any]) -> None:
        """Update context with API response data.

        Stores response in state.last_response for template access.
        """
        self.state.set("last_response", response)

    def set_logic_values(self, values: dict[str, Any]) -> None:
        """Set multiple logic values at once.

        Args:
            values: Dict of logic values (keys without 'logic.' prefix)
        """
        for key, value in values.items():
            # Handle both 'logic.foo' and 'foo' formats
            if key.startswith("logic."):
                self.set(key, value)
            else:
                self.logic.set(key, value)
