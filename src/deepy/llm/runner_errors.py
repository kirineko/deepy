from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DeepSeekErrorStatus:
    title: str
    reason: str
    suggestion: str


DEEPSEEK_ERROR_CODES: dict[int, DeepSeekErrorStatus] = {
    400: DeepSeekErrorStatus(
        title="格式错误",
        reason="请求体格式错误。",
        suggestion="请根据错误信息提示修改请求体。",
    ),
    401: DeepSeekErrorStatus(
        title="认证失败",
        reason="API key 错误，认证失败。",
        suggestion="请检查 API key 是否正确；如果还没有 API key，请先创建 API key。",
    ),
    402: DeepSeekErrorStatus(
        title="余额不足",
        reason="账号余额不足。",
        suggestion="请确认账户余额，并前往 DeepSeek 充值页面充值。",
    ),
    422: DeepSeekErrorStatus(
        title="参数错误",
        reason="请求体参数错误。",
        suggestion="请根据错误信息提示修改相关参数。",
    ),
    429: DeepSeekErrorStatus(
        title="请求速率达到上限",
        reason="请求速率（TPM 或 RPM）达到上限。",
        suggestion="请合理规划请求速率，稍后重试。",
    ),
    500: DeepSeekErrorStatus(
        title="服务器故障",
        reason="DeepSeek 服务器内部故障。",
        suggestion="请等待后重试；如果问题持续存在，请联系 DeepSeek 支持。",
    ),
    503: DeepSeekErrorStatus(
        title="服务器繁忙",
        reason="服务器负载过高。",
        suggestion="请稍后重试请求。",
    ),
}


def format_deepseek_api_error(error: Any) -> str:
    status_code = _safe_int(getattr(error, "status_code", None))
    status = DEEPSEEK_ERROR_CODES.get(status_code) if status_code is not None else None
    title = f"DeepSeek API error {status_code}" if status_code is not None else "DeepSeek API error"
    if status is not None:
        title = f"{title}: {status.title}"

    lines = [title]
    server_message = _api_status_error_message(error)
    if server_message:
        lines.extend(["", f"Server message: {server_message}"])
    if status is not None:
        lines.extend(["", f"Reason: {status.reason}", f"Suggestion: {status.suggestion}"])

    error_code = _api_error_body_field(error, "code")
    error_type = _api_error_body_field(error, "type")
    if error_code or error_type:
        detail_parts = [
            part
            for part in (
                f"code={error_code}" if error_code else "",
                f"type={error_type}" if error_type else "",
            )
            if part
        ]
        detail = ", ".join(detail_parts)
        lines.append(f"Detail: {detail}")
    return "\n".join(lines)


def _api_status_error_message(error: Any) -> str:
    body_message = _api_error_body_field(error, "message")
    if body_message:
        return body_message
    message = getattr(error, "message", None)
    return str(message).strip() if message else str(error).strip()


def _api_status_error_response(error: Any) -> dict[str, Any]:
    response = getattr(error, "response", None)
    result: dict[str, Any] = {}
    status_code = _safe_int(getattr(error, "status_code", None))
    if status_code is not None:
        result["statusCode"] = status_code
    request_id = getattr(error, "request_id", None)
    if request_id:
        result["requestId"] = request_id
    body = getattr(error, "body", None)
    if body is not None:
        result["body"] = body
    if response is not None:
        url = getattr(response, "url", None)
        if url is not None:
            result["url"] = str(url)
    return result


def _api_error_body_field(error: Any, field: str) -> str:
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        body_error = body.get("error")
        if isinstance(body_error, dict):
            value = body_error.get(field)
            return str(value).strip() if value is not None else ""
        value = body.get(field)
        return str(value).strip() if value is not None else ""
    return ""


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
