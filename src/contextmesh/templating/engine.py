"""Template engine for resolving {{path}} expressions using context."""

import re
from typing import Any

from contextmesh.core.context import RuntimeContext
from contextmesh.utils.exceptions import ContextPathError, TemplateResolutionError


class TemplateEngine:
    """Engine for resolving template expressions like {{db.customer.id}}."""

    # Pattern to match {{path}} expressions
    TEMPLATE_PATTERN = re.compile(r"\{\{([^}]+)\}\}")

    def resolve(self, template: str, context: RuntimeContext) -> Any:
        """Resolve a template string using context.

        If the template is just a single {{path}} expression, returns the actual
        value (preserving type). If the template contains multiple expressions
        or text around expressions, returns a string with substitutions.

        Args:
            template: Template string (e.g., '{{db.customer.id}}')
            context: RuntimeContext to resolve values from

        Returns:
            Resolved value (type preserved for single expressions)

        Raises:
            TemplateResolutionError: If template cannot be resolved
        """
        template = template.strip()

        # Check if it's a single expression (just {{path}})
        single_match = self.TEMPLATE_PATTERN.fullmatch(template)
        if single_match:
            path = single_match.group(1).strip()
            return self._resolve_path(path, context)

        # Multiple expressions or mixed content - return string
        def replace_match(match: re.Match) -> str:
            path = match.group(1).strip()
            value = self._resolve_path(path, context)
            return str(value)

        try:
            return self.TEMPLATE_PATTERN.sub(replace_match, template)
        except Exception as e:
            raise TemplateResolutionError(f"Failed to resolve template '{template}': {e}")

    def resolve_dict(
        self, template_dict: dict[str, str], context: RuntimeContext
    ) -> dict[str, Any]:
        """Resolve all template values in a dictionary.

        Args:
            template_dict: Dict with template strings as values
            context: RuntimeContext to resolve values from

        Returns:
            Dict with resolved values
        """
        result: dict[str, Any] = {}

        for key, value in template_dict.items():
            if isinstance(value, str):
                result[key] = self.resolve(value, context)
            elif isinstance(value, dict):
                # Recursively resolve nested dicts
                result[key] = self.resolve_dict(value, context)
            else:
                result[key] = value

        return result

    def resolve_params(
        self,
        template_params: dict[str, Any],
        context: RuntimeContext,
        strict: bool = False,
    ) -> dict[str, Any]:
        """Resolve template parameters for an API call.

        Args:
            template_params: Parameter templates from x-contextMesh
            context: RuntimeContext to resolve values from
            strict: If True, raise on missing values; if False, skip them

        Returns:
            Dict of resolved parameter values
        """
        result: dict[str, Any] = {}

        for key, template in template_params.items():
            try:
                if isinstance(template, str):
                    result[key] = self.resolve(template, context)
                elif isinstance(template, dict):
                    # Recursively resolve nested dicts
                    result[key] = self.resolve_params(template, context, strict)
                else:
                    # Pass through non-string, non-dict values as-is
                    result[key] = template
            except (TemplateResolutionError, ContextPathError) as e:
                if strict:
                    raise
                # Skip parameters that can't be resolved in non-strict mode

        return result

    def validate_template(self, template: str) -> bool:
        """Check if a template string is valid.

        Args:
            template: Template string to validate

        Returns:
            True if template syntax is valid
        """
        # Check for balanced braces
        open_count = template.count("{{")
        close_count = template.count("}}")

        if open_count != close_count:
            return False

        # Check each expression has a valid path
        for match in self.TEMPLATE_PATTERN.finditer(template):
            path = match.group(1).strip()
            if not self._is_valid_path(path):
                return False

        return True

    def extract_paths(self, template: str) -> list[str]:
        """Extract all context paths from a template.

        Args:
            template: Template string

        Returns:
            List of context paths (e.g., ['db.customer.id', 'state.case_id'])
        """
        paths = []
        for match in self.TEMPLATE_PATTERN.finditer(template):
            path = match.group(1).strip()
            paths.append(path)
        return paths

    def _resolve_path(self, path: str, context: RuntimeContext) -> Any:
        """Resolve a single context path.

        Args:
            path: Context path (e.g., 'db.customer.id')
            context: RuntimeContext

        Returns:
            Value at the path

        Raises:
            TemplateResolutionError: If path cannot be resolved
        """
        # Handle special response path
        if path.startswith("response."):
            remaining = path[9:]  # Remove 'response.' prefix
            try:
                return context.state.get(f"last_response.{remaining}")
            except ContextPathError:
                raise TemplateResolutionError(
                    f"Response path not found: {path}. "
                    "Make sure an API response has been received."
                )

        try:
            return context.get(path)
        except ContextPathError as e:
            raise TemplateResolutionError(f"Failed to resolve path '{path}': {e}")

    def _is_valid_path(self, path: str) -> bool:
        """Check if a path string is valid format."""
        if not path:
            return False

        # Must start with a valid namespace or 'response'
        valid_prefixes = ("db.", "state.", "input.", "logic.", "response.")
        return any(path.startswith(prefix) for prefix in valid_prefixes)


def resolve_template(template: str, context: RuntimeContext) -> Any:
    """Convenience function to resolve a template.

    Args:
        template: Template string
        context: RuntimeContext

    Returns:
        Resolved value
    """
    engine = TemplateEngine()
    return engine.resolve(template, context)
