"""Unit tests for knowledge service."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.services.knowledge import KnowledgeService


@pytest.fixture
def temp_knowledge_dir(tmp_path):
    """Create temporary knowledge directory with test files."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()

    # Create INDEX.md
    index_content = """# Knowledge Index

## Agent Type Tags

- **campaign_health**: account_structure.md, strategy_brand.md
- **keyword**: account_structure.md, product_info.md

## Campaign Type Tags

- **brand**: strategy_brand.md, account_structure.md
- **non_brand**: strategy_nonbrand.md
"""
    (knowledge_dir / "INDEX.md").write_text(index_content)

    # Create knowledge files
    (knowledge_dir / "account_structure.md").write_text("# Account Structure\n\nTest account structure content.")
    (knowledge_dir / "strategy_brand.md").write_text("# Brand Strategy\n\nTest brand strategy content.")
    (knowledge_dir / "product_info.md").write_text("# Product Info\n\nTest product info content.")
    (knowledge_dir / "strategy_nonbrand.md").write_text("# NonBrand Strategy\n\nTest nonbrand strategy content.")

    return str(knowledge_dir)


def test_knowledge_service_init(temp_knowledge_dir):
    """Test KnowledgeService initialization."""
    service = KnowledgeService(knowledge_dir=temp_knowledge_dir)

    assert service.knowledge_dir == Path(temp_knowledge_dir)
    assert service._file_cache == {}
    assert service._index_cache == {}


def test_load_index(temp_knowledge_dir):
    """Test INDEX.md parsing."""
    service = KnowledgeService(knowledge_dir=temp_knowledge_dir)
    service._load_index()

    assert "campaign_health" in service._index_cache
    assert "account_structure.md" in service._index_cache["campaign_health"]
    assert "strategy_brand.md" in service._index_cache["campaign_health"]

    assert "keyword" in service._index_cache
    assert "product_info.md" in service._index_cache["keyword"]


def test_load_file(temp_knowledge_dir):
    """Test individual file loading."""
    service = KnowledgeService(knowledge_dir=temp_knowledge_dir)

    content = service._load_file("account_structure.md")

    assert content is not None
    assert "Test account structure content" in content


def test_load_file_caching(temp_knowledge_dir):
    """Test file content caching."""
    service = KnowledgeService(knowledge_dir=temp_knowledge_dir)

    # Load file twice
    content1 = service._load_file("account_structure.md")
    content2 = service._load_file("account_structure.md")

    assert content1 == content2
    assert "account_structure.md" in service._file_cache


def test_load_file_not_found(temp_knowledge_dir):
    """Test loading nonexistent file."""
    service = KnowledgeService(knowledge_dir=temp_knowledge_dir)

    content = service._load_file("nonexistent.md")

    assert content is None


def test_get_context_for_agent(temp_knowledge_dir):
    """Test getting context for specific agent type."""
    service = KnowledgeService(knowledge_dir=temp_knowledge_dir)

    context = service.get_context(agent_type="campaign_health")

    assert "account_structure.md" in context
    assert "strategy_brand.md" in context
    assert "Test account structure content" in context
    assert "Test brand strategy content" in context


def test_get_context_with_campaign_type(temp_knowledge_dir):
    """Test getting context with campaign type tag."""
    service = KnowledgeService(knowledge_dir=temp_knowledge_dir)

    context = service.get_context(
        agent_type="campaign_health",
        campaign_type="brand",
    )

    assert "strategy_brand.md" in context
    assert "account_structure.md" in context
    assert "Test brand strategy content" in context


def test_get_context_deduplication(temp_knowledge_dir):
    """Test that files are not duplicated in context."""
    service = KnowledgeService(knowledge_dir=temp_knowledge_dir)

    # Both campaign_health and brand tags include account_structure.md
    context = service.get_context(
        agent_type="campaign_health",
        campaign_type="brand",
    )

    # Count occurrences of the section header
    count = context.count("## account_structure.md")
    assert count == 1  # Should appear only once despite being in both tags


def test_get_context_truncation(temp_knowledge_dir):
    """Test context truncation when exceeding max_chars."""
    service = KnowledgeService(knowledge_dir=temp_knowledge_dir)

    # Request context with very low max_chars
    context = service.get_context(
        agent_type="campaign_health",
        max_chars=100,
    )

    assert len(context) <= 150  # Allow some margin for truncation message
    assert "[Content truncated...]" in context


def test_get_context_with_conversion_goal(temp_knowledge_dir):
    """Test getting context with conversion goal tag."""
    # Add conversion goal tag to INDEX
    index_path = Path(temp_knowledge_dir) / "INDEX.md"
    index_content = index_path.read_text()
    index_content += "\n## Conversion Goal Tags\n\n- **conversion_sqc_org_creates**: product_info.md\n"
    index_path.write_text(index_content)

    service = KnowledgeService(knowledge_dir=temp_knowledge_dir)

    context = service.get_context(
        agent_type="campaign_health",
        conversion_goal="sqc_org_creates",
    )

    assert "product_info.md" in context


def test_get_files_for_tags(temp_knowledge_dir):
    """Test _get_files_for_tags method."""
    service = KnowledgeService(knowledge_dir=temp_knowledge_dir)

    files = service._get_files_for_tags(["campaign_health", "brand"])

    # Should include files from both tags, deduplicated
    assert "account_structure.md" in files
    assert "strategy_brand.md" in files
    # account_structure.md should appear only once despite being in both tags
    assert files.count("account_structure.md") == 1


def test_index_not_found_graceful_handling(tmp_path):
    """Test graceful handling when INDEX.md doesn't exist."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    service = KnowledgeService(knowledge_dir=str(empty_dir))
    service._load_index()

    # Should not raise, just have empty index
    assert service._index_cache == {}


def test_get_context_with_missing_files(temp_knowledge_dir):
    """Test context generation when some files are missing."""
    service = KnowledgeService(knowledge_dir=temp_knowledge_dir)

    # Manually set index to include a nonexistent file
    service._index_cache = {
        "test": ["existing.md", "nonexistent.md"]
    }

    # Create only the existing file
    (Path(temp_knowledge_dir) / "existing.md").write_text("Existing content")

    context = service.get_context(agent_type="test")

    # Should include existing file content, skip missing file
    assert "Existing content" in context
    assert "nonexistent.md" not in context  # Header shouldn't appear
