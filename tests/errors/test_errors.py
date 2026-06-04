from __future__ import annotations

from deepy.errors import classify_error, format_error_display


class ErrorWithStatus(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def test_classify_error_identifies_api_auth_errors():
    display = classify_error(ErrorWithStatus(401, "invalid api key"))

    assert display.category == "api_auth"
    assert "deepy config setup" in display.hint


def test_classify_error_identifies_network_errors():
    display = classify_error(TimeoutError("request timed out"))

    assert display.category == "network"


def test_format_error_display_includes_category_and_hint():
    text = format_error_display("missing api_key in config")

    assert text.startswith("config:")
    assert "Hint: Run `deepy config setup`." in text
