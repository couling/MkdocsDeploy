from typing import Any, NamedTuple, TypeVar
from copy import deepcopy

_T = TypeVar("_T")


class MethodCall(NamedTuple):
    name: str | None
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


def mock_wrapper(to_wrap: _T) -> tuple[_T, list[MethodCall]]:
    method_calls: list[MethodCall] = []
    return _MockWrapper(to_wrap, method_calls), method_calls # type: ignore


class _MockWrapper:

    _wrapped = None
    _name = None
    _method_calls = None

    def __init__(self, wrapped: Any, method_calls: list[MethodCall], name: str | None = None):
        self._name = name
        self._wrapped = wrapped
        self._method_calls = method_calls

    def __getattr__(self, item):
        result = getattr(self._wrapped, item)
        if hasattr(result, "__call__"):
            return type(self)(wrapped=result, method_calls=self._method_calls, name=item)
        return result

    def __setattr__(self, key, value):
        if key in ("_wrapped", "_method_calls", "_name"):
            return super().__setattr__(key, value)
        return setattr(self._wrapped, key, value)

    def __call__(self, *args, **kwargs):
        self._method_calls.append(MethodCall(self._name, args, kwargs))
        return self._wrapped(*args, **kwargs)
