import logging
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ParamSpec,
    TypeVar,
)

import loguru
from loguru import logger
from sdk_creator.errors import ApiRaisedFromStatusError

_P = ParamSpec("_P")
_R = TypeVar("_R")


def ensure_entity_exist(
    param_name: str,
    error_class: type[Exception],
    entity_type: str,
    error_message_template: str = "{entity_type} with id {entity_id} not found",
) -> Callable[[Callable[_P, Awaitable[_R]]], Callable[_P, Awaitable[_R]]]:
    """Generic decorator to raise custom error if entity is not found."""

    def decorator(coro: Callable[_P, Awaitable[_R]]) -> Callable[_P, Awaitable[_R]]:
        @wraps(coro)
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            entity_id = kwargs.get(param_name)
            if entity_id is None:
                import inspect

                sig = inspect.signature(coro)
                param_names = list(sig.parameters.keys())
                try:
                    param_index = param_names.index(param_name)
                    if param_index < len(args):
                        entity_id = args[param_index]
                except (ValueError, IndexError):
                    pass

            if entity_id is None:
                raise ValueError(f"Function must have '{param_name}' parameter")

            try:
                return await coro(*args, **kwargs)
            except ApiRaisedFromStatusError as err:
                if err.status_code != 404:
                    raise

                logger.error(f"{entity_type} not found: {entity_id}")
                error_message = error_message_template.format(
                    entity_type=entity_type, entity_id=entity_id
                )
                raise error_class(error_message) from err

        return wrapper

    return decorator


def map_error(
    catch: type[Exception], raise_: type[Exception]
) -> Callable[[Callable[_P, Awaitable[_R]]], Callable[_P, Awaitable[_R]]]:
    """Obscure the Api raised errors to a more understandable sdk related error.

    For example, if a ApiRaisedFromStatus with status_code=400 error occurred it would
    be mapped to 'raise_' which could be a FaceError or PersonDirectoryError
    as an example
    """

    def decorator(coro: Callable[_P, Awaitable[_R]]) -> Callable[_P, Awaitable[_R]]:
        @wraps(coro)
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            try:
                return await coro(*args, **kwargs)
            except catch as err:
                raise raise_ from err

        return wrapper

    return decorator


if TYPE_CHECKING:
    _LogRecord = loguru.Record
else:
    _LogRecord = Any


_LogLevels = Annotated[
    int | str | set[int | str],
    "Log level(s) to suppress. Can be single level or set of levels",
]


def _logging_level_name_to_level_no(level_name: str) -> int:
    return getattr(logging, level_name.upper())


def _suppress_all_module_logs(module_name: str) -> Generator[None, None]:
    logger.disable(module_name)

    try:
        yield
    finally:
        logger.enable(module_name)

    return


@contextmanager
def suppress_logs(
    target: Annotated[
        str, "Targeted module name to suppress logger messages emitted from"
    ],
    levels: _LogLevels | None = None,
) -> Generator[None, None]:
    """Context manager to suppress logs emitted from a certain module momentarily."""
    if levels is None:
        yield from _suppress_all_module_logs(target)
        return

    def normalize_levels(levels: _LogLevels) -> set[int]:
        if not isinstance(levels, set):
            levels = {levels}

        return {
            _logging_level_name_to_level_no(level) if isinstance(level, str) else level
            for level in levels
        }

    normalized_levels = normalize_levels(levels)

    # FIXME: level filter process not working
    def selective_filter(record: _LogRecord) -> bool:
        nonlocal target, normalized_levels
        module_name_match = record["name"] == target
        levels_suppress_match = record["level"].no in list(
            range(logging.NOTSET, max(normalized_levels) + 10, 10)
        )
        return not (module_name_match and levels_suppress_match)

    # null sink discards messages
    null_sink = lambda _: None  # noqa

    filter_id = logger.add(null_sink, filter=selective_filter, level=logging.NOTSET)

    try:
        yield
    finally:
        logger.remove(filter_id)
