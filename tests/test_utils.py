import pytest

from instagram_analyzer.utils import normalize_username


@pytest.mark.parametrize(
    "value",
    [
        "https://www.instagram.com/example/",
        "https://instagram.com/example",
        "https://instagram.com/example/?igsh=test",
        "@example",
        "example",
    ],
)
def test_normalize_username(value: str) -> None:
    assert normalize_username(value) == "example"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "https://example.com/example",
        "https://instagram.com/p/abc123",
        "https://instagram.com/example/posts",
        "invalid username",
        "@",
    ],
)
def test_normalize_username_rejects_invalid_input(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_username(value)

