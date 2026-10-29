from __future__ import annotations


def exception_type_name(error: BaseException) -> str:
    """Return an exception category without rendering its sensitive message."""

    return type(error).__name__
