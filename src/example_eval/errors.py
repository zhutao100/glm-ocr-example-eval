from __future__ import annotations


class ExampleEvalError(Exception):
    """User-facing error for invalid inputs/configuration.

    The CLI catches this and exits non-zero with a concise message.
    """
