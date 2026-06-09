"""Pytest configuration and fixtures."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def app():
    """Create test application."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_html():
    """Sample HTML for testing."""
    return """
    <html>
    <head><title>Test Page</title></head>
    <body>
        <header>
            <h1>Welcome</h1>
            <nav>
                <a href="/">Home</a>
                <a href="/about">About</a>
            </nav>
        </header>
        <main>
            <article>
                <h2>First Post</h2>
                <p>This is the first post content.</p>
            </article>
            <article>
                <h2>Second Post</h2>
                <p>This is the second post content.</p>
            </article>
        </main>
        <footer>
            <p>Copyright 2024</p>
        </footer>
    </body>
    </html>
    """
