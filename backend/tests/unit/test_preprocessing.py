"""Tests for preprocessing modules."""
import pytest

from app.preprocessing.cleaner import clean_html
from app.preprocessing.id_anchoring import assign_element_ids
from app.preprocessing.skeletonizer import skeletonize_html


def test_clean_html_removes_scripts():
    """Test that script tags are cleaned."""
    html = "<html><body><script>alert('test')</script><p>Content</p></body></html>"
    cleaned = clean_html(html)
    assert "<script>" in cleaned  # Tag remains
    assert "alert" not in cleaned  # Content removed


def test_clean_html_removes_comments():
    """Test that HTML comments are removed."""
    html = "<html><body><!-- Comment --><p>Content</p></body></html>"
    cleaned = clean_html(html)
    assert "Comment" not in cleaned


def test_assign_element_ids():
    """Test element ID assignment."""
    html = "<html><body><div><p>Test</p></div></body></html>"
    html_with_ids, id_map = assign_element_ids(html)
    
    assert "data-element-id" in html_with_ids
    assert len(id_map) > 0
    assert all(key.startswith("e") for key in id_map.keys())


def test_skeletonize_html():
    """Test HTML skeletonization."""
    long_text = "a" * 100
    html = f"<html><body><p>{long_text}</p></body></html>"
    skeletonized = skeletonize_html(html, max_text_length=50)
    
    assert "[text:" in skeletonized
    assert long_text not in skeletonized

# Made with Bob
