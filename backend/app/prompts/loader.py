"""Prompt template loader with caching."""
import os
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, Template

from ..core.tracing import get_logger

logger = get_logger(__name__)


class PromptLoader:
    """Loads and caches prompt templates from the prompts directory."""

    def __init__(self, prompts_dir: str | Path | None = None):
        """
        Initialize the prompt loader.
        
        Args:
            prompts_dir: Path to prompts directory (defaults to app/prompts)
        """
        if prompts_dir is None:
            # Default to app/prompts directory
            current_file = Path(__file__)
            prompts_dir = current_file.parent

        self.prompts_dir = Path(prompts_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            autoescape=False,  # We're generating prompts, not HTML
        )
        self.manifests: dict[str, dict[str, Any]] = {}
        self.templates: dict[str, Template] = {}
        self.examples: dict[str, list[dict[str, Any]]] = {}

    def load_all_manifests(self) -> None:
        """Load all manifest.yaml files from handler directories."""
        for handler_dir in self.prompts_dir.iterdir():
            if not handler_dir.is_dir():
                continue

            manifest_path = handler_dir / "manifest.yaml"
            if manifest_path.exists():
                try:
                    self._load_manifest(handler_dir.name, manifest_path)
                except Exception as e:
                    logger.error(f"Failed to load manifest for {handler_dir.name}: {e}")

    def _load_manifest(self, handler_name: str, manifest_path: Path) -> None:
        """Load a single manifest file."""
        with open(manifest_path, "r") as f:
            manifest = yaml.safe_load(f)

        self.manifests[handler_name] = manifest

        # Get active version
        active_version = manifest.get("active_version", "v1")
        version_config = manifest.get("versions", {}).get(active_version, {})

        # Load templates for active version
        handler_dir = manifest_path.parent
        for template_type in ["system", "user"]:
            template_file = version_config.get(template_type)
            if template_file:
                template_path = handler_dir / template_file
                if template_path.exists():
                    template_key = f"{handler_name}.{template_type}"
                    self.templates[template_key] = self.env.get_template(
                        f"{handler_name}/{template_file}"
                    )
                    logger.info(f"Loaded template: {template_key}")

        # Load examples if present
        examples_file = version_config.get("examples")
        if examples_file:
            examples_path = handler_dir / examples_file
            if examples_path.exists():
                with open(examples_path, "r") as f:
                    self.examples[handler_name] = yaml.safe_load(f)
                logger.info(f"Loaded examples for {handler_name}")

        logger.info(f"Loaded manifest for handler: {handler_name}")

    def get_template(self, handler_name: str, template_type: str) -> Template | None:
        """
        Get a template by handler name and type.
        
        Args:
            handler_name: Name of the handler
            template_type: Type of template ('system' or 'user')
            
        Returns:
            Jinja2 Template or None if not found
        """
        template_key = f"{handler_name}.{template_type}"
        return self.templates.get(template_key)

    def get_examples(self, handler_name: str) -> list[dict[str, Any]]:
        """
        Get few-shot examples for a handler.
        
        Args:
            handler_name: Name of the handler
            
        Returns:
            List of example dicts
        """
        return self.examples.get(handler_name, [])

    def get_manifest(self, handler_name: str) -> dict[str, Any] | None:
        """
        Get the manifest for a handler.
        
        Args:
            handler_name: Name of the handler
            
        Returns:
            Manifest dict or None if not found
        """
        return self.manifests.get(handler_name)

    def render_template(
        self, handler_name: str, template_type: str, **context: Any
    ) -> str | None:
        """
        Render a template with context.
        
        Args:
            handler_name: Name of the handler
            template_type: Type of template ('system' or 'user')
            **context: Template context variables
            
        Returns:
            Rendered template string or None if template not found
        """
        template = self.get_template(handler_name, template_type)
        if template is None:
            return None
        return template.render(**context)


# Global prompt loader instance
_prompt_loader: PromptLoader | None = None


def get_prompt_loader() -> PromptLoader:
    """Get the global prompt loader instance."""
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
        _prompt_loader.load_all_manifests()
    return _prompt_loader
