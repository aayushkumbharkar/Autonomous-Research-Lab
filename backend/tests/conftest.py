"""Test fixtures and configuration."""

import pytest
import asyncio
from unittest.mock import patch


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
