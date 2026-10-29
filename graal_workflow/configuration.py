"""Read scalar launch defaults, using the CLI actions as the option schema."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import re

import yaml


class _ConfigLoader(yaml.SafeLoader):
    """Safe YAML with unique string keys and true/false booleans only."""

    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise yaml.constructor.ConstructorError(
                    None, None, "configuration keys must be strings", key_node.start_mark,
                )
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate configuration key: {key}", key_node.start_mark,
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


# PyYAML otherwise treats unquoted `off` (a flux-study choice) as False.
# Copy resolvers so other YAML consumers keep their own parsing behavior.
_ConfigLoader.yaml_implicit_resolvers = {
    key: [(tag, pattern) for tag, pattern in resolvers
          if tag != "tag:yaml.org,2002:bool"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_ConfigLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$", re.IGNORECASE), list("tTfF"),
)


def load_config(path: Path, actions: Sequence[argparse.Action]) -> dict:
    """Validate every supplied default, including ones later overridden by CLI.

    Options are scalar: their existing CLI defaults define the scalar type;
    Path converters additionally require nonempty strings, relative to this file.
    Choices and converters come from the same actions used for CLI arguments.
    """
    path = path.expanduser().resolve()
    values, _ = read_config(path)
    options = {action.dest: action for action in actions
               if action.option_strings and action.dest != "help"}
    result = {}
    for key, value in values.items():
        if key not in options:
            raise ValueError(f"{path}: unknown configuration key: {key}")
        action = options[key]
        expected = type(action.default) if action.default is not None else str
        if type(value) is not expected:
            raise ValueError(f"{path}: {key} must be {expected.__name__}, got {type(value).__name__}")
        if action.choices is not None and value not in action.choices:
            raise ValueError(f"{path}: {key} must be one of {', '.join(map(str, action.choices))}")
        if action.type is Path:
            if not value.strip():
                raise ValueError(f"{path}: {key} must be a nonempty path")
            value = Path(value).expanduser()
            value = (path.parent / value).resolve() if not value.is_absolute() else value
        elif action.type is not None:
            try:
                value = action.type(value)
            except (ValueError, TypeError, argparse.ArgumentTypeError) as exc:
                raise ValueError(f"{path}: invalid {key}: {exc}") from exc
        result[key] = value
    return result


def read_config(path: Path) -> tuple[dict, str]:
    """Read one safe, duplicate-free YAML mapping and retain its exact source."""
    path = path.expanduser().resolve()
    try:
        source_text = path.read_text(encoding="utf-8")
        values = yaml.load(source_text, Loader=_ConfigLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"{path}: cannot read YAML configuration: {exc}") from exc
    if not isinstance(values, dict):
        raise ValueError(f"{path}: configuration must be a mapping of option names to values")
    return values, source_text
