from __future__ import annotations

from copy import deepcopy
from typing import Any


def make_mimo_compatible_tool_schema(schema: dict[str, Any]) -> dict[str, Any]:
    compatible = deepcopy(schema)
    _remove_nullable_required_fields(compatible)
    return compatible


def _remove_nullable_required_fields(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _remove_nullable_required_fields(item)
        return
    if not isinstance(value, dict):
        return

    properties = value.get("properties")
    required = value.get("required")
    if isinstance(properties, dict) and isinstance(required, list):
        value["required"] = [
            field
            for field in required
            if not (
                isinstance(field, str)
                and isinstance(properties.get(field), dict)
                and _schema_type_allows_null(properties[field])
            )
        ]

    if _schema_type_allows_null(value):
        schema_type = value["type"]
        non_null_types = [item for item in schema_type if item != "null"]
        if len(non_null_types) == 1:
            value["type"] = non_null_types[0]
        elif non_null_types:
            value["type"] = non_null_types

    for item in value.values():
        _remove_nullable_required_fields(item)


def _schema_type_allows_null(schema: dict[str, Any]) -> bool:
    schema_type = schema.get("type")
    return isinstance(schema_type, list) and "null" in schema_type


def _validate_args_against_schema(args: dict[str, Any], schema: dict[str, Any]) -> str | None:
    required = schema.get("required")
    if isinstance(required, list):
        for field in required:
            if isinstance(field, str) and field not in args:
                return f"Missing required field: {field}"
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return None
    if schema.get("additionalProperties") is False:
        extra = sorted(set(args) - set(properties))
        if extra:
            return f"Unsupported fields: {', '.join(extra)}"
    for key, value in args.items():
        field_schema = properties.get(key)
        if isinstance(field_schema, dict) and not _schema_value_matches(value, field_schema):
            return f"Invalid type for field: {key}"
    return None


def _schema_value_matches(value: Any, schema: dict[str, Any]) -> bool:
    schema_type = schema.get("type")
    allowed = schema_type if isinstance(schema_type, list) else [schema_type]
    if value is None:
        return "null" in allowed
    if "string" in allowed and isinstance(value, str):
        return _schema_enum_matches(value, schema)
    if "boolean" in allowed and isinstance(value, bool):
        return _schema_enum_matches(value, schema)
    if "integer" in allowed and isinstance(value, int) and not isinstance(value, bool):
        return _schema_enum_matches(value, schema)
    if "number" in allowed and isinstance(value, int | float) and not isinstance(value, bool):
        return _schema_enum_matches(value, schema)
    if "array" in allowed and isinstance(value, list):
        item_schema = schema.get("items")
        return not isinstance(item_schema, dict) or all(_schema_value_matches(item, item_schema) for item in value)
    if "object" in allowed and isinstance(value, dict):
        nested_error = _validate_args_against_schema(value, schema)
        return nested_error is None
    return False


def _schema_enum_matches(value: Any, schema: dict[str, Any]) -> bool:
    enum = schema.get("enum")
    return not isinstance(enum, list) or value in enum
