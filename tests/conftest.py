from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_bytes():
    def _load(*parts: str) -> bytes:
        return (FIXTURES_DIR.joinpath(*parts)).read_bytes()

    return _load
