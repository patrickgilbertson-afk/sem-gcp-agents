"""Knowledge service for loading business context into agent prompts."""

import os
from pathlib import Path
from typing import Set

import structlog

logger = structlog.get_logger(__name__)


class KnowledgeService:
    """Service for loading knowledge files into agent context.

    Lightweight loader that parses INDEX.md to find relevant files by tag,
    loads and deduplicates content, and injects into LLM prompts.
    """

    def __init__(self, knowledge_dir: str | None = None):
        """Initialize knowledge service.

        Args:
            knowledge_dir: Path to knowledge directory (defaults to docs/knowledge)
        """
        if knowledge_dir is None:
            # Default to docs/knowledge relative to project root
            project_root = Path(__file__).parent.parent.parent
            knowledge_dir = str(project_root / "docs" / "knowledge")

        self.knowledge_dir = Path(knowledge_dir)
        self.logger = logger.bind(component="knowledge_service")
        self._file_cache: dict[str, str] = {}
        self._index_cache: dict[str, list[str]] = {}

    def get_context(
        self,
        agent_type: str,
        campaign_type: str | None = None,
        conversion_goal: str | None = None,
        max_chars: int = 15000,
    ) -> str:
        """Get knowledge context for an agent.

        Args:
            agent_type: Type of agent (e.g., "campaign_health")
            campaign_type: Optional campaign type (e.g., "brand", "non_brand")
            conversion_goal: Optional conversion goal (e.g., "sqc_org_creates")
            max_chars: Maximum character budget for context

        Returns:
            Formatted knowledge context string
        """
        self.logger.info(
            "loading_knowledge_context",
            agent_type=agent_type,
            campaign_type=campaign_type,
            conversion_goal=conversion_goal,
        )

        # Build list of tags to query
        tags = [agent_type]
        if campaign_type:
            tags.append(campaign_type)
        if conversion_goal:
            tags.append(f"conversion_{conversion_goal.lower()}")

        # Get relevant files from INDEX
        files = self._get_files_for_tags(tags)

        # Load and deduplicate file contents
        content_sections = []
        seen_files: Set[str] = set()

        for file in files:
            if file not in seen_files:
                content = self._load_file(file)
                if content:
                    content_sections.append(f"## {file}\n\n{content}")
                    seen_files.add(file)

        # Concatenate and truncate if needed
        full_context = "\n\n---\n\n".join(content_sections)

        if len(full_context) > max_chars:
            self.logger.warning(
                "knowledge_context_truncated",
                original_length=len(full_context),
                max_chars=max_chars,
            )
            full_context = full_context[:max_chars] + "\n\n[Content truncated...]"

        self.logger.info(
            "knowledge_context_loaded",
            files_loaded=len(seen_files),
            total_chars=len(full_context),
        )

        return full_context

    def _get_files_for_tags(self, tags: list[str]) -> list[str]:
        """Get list of knowledge files for given tags.

        Args:
            tags: List of tags to query (agent_type, campaign_type, etc.)

        Returns:
            List of filenames
        """
        # Load INDEX.md if not cached
        if not self._index_cache:
            self._load_index()

        # Collect files for all tags
        files: list[str] = []
        for tag in tags:
            tag_files = self._index_cache.get(tag.lower(), [])
            files.extend(tag_files)

        # Return unique files in order
        seen: Set[str] = set()
        unique_files = []
        for f in files:
            if f not in seen:
                unique_files.append(f)
                seen.add(f)

        return unique_files

    def _load_index(self) -> None:
        """Load INDEX.md and parse tag-to-file mappings."""
        index_path = self.knowledge_dir / "INDEX.md"

        if not index_path.exists():
            self.logger.warning("index_not_found", path=str(index_path))
            return

        try:
            content = index_path.read_text(encoding="utf-8")

            # Parse lines like "- **campaign_health**: file1.md, file2.md"
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("- **"):
                    # Extract tag and files
                    parts = line.split(":")
                    if len(parts) >= 2:
                        # Extract tag between ** **
                        tag = parts[0].replace("- **", "").replace("**", "").strip().lower()

                        # Extract files (comma-separated)
                        files_str = ":".join(parts[1:]).strip()
                        files = [f.strip() for f in files_str.split(",")]

                        self._index_cache[tag] = files

            self.logger.info("index_loaded", tags_found=len(self._index_cache))

        except Exception as e:
            self.logger.error("index_load_failed", error=str(e))

    def _load_file(self, filename: str) -> str | None:
        """Load a knowledge file.

        Args:
            filename: Name of file to load (e.g., "account_structure.md")

        Returns:
            File contents or None if not found
        """
        # Check cache first
        if filename in self._file_cache:
            return self._file_cache[filename]

        file_path = self.knowledge_dir / filename

        if not file_path.exists():
            self.logger.warning("knowledge_file_not_found", filename=filename)
            return None

        try:
            content = file_path.read_text(encoding="utf-8")
            self._file_cache[filename] = content
            return content

        except Exception as e:
            self.logger.error("file_load_failed", filename=filename, error=str(e))
            return None
