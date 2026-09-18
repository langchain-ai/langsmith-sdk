"""Inline generator runtime for shared sync and async effects."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Coroutine, Generator
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, Union, cast

_ResultT = TypeVar("_ResultT")


@dataclass(frozen=True)
class Call(Generic[_ResultT]):
    """A deferred callable that can be delegated to with yield from."""

    effect: Callable[[], Union[_ResultT, Awaitable[_ResultT]]]

    def __call__(self) -> Union[_ResultT, Awaitable[_ResultT]]:
        """Invoke the deferred callable."""
        return self.effect()

    def __iter__(self) -> Generator[Call[Any], Any, _ResultT]:
        """Delegate this call from an effect program."""
        return cast(_ResultT, (yield self))


Program = Generator[Call[Any], Any, _ResultT]


def run_sync(program: Program[_ResultT]) -> _ResultT:
    """Run an effect program with synchronous calls."""
    try:
        try:
            current = next(program)
        except StopIteration as done:
            return cast(_ResultT, done.value)
        while True:
            try:
                value = current()
                if inspect.isawaitable(value):
                    if isinstance(value, Coroutine):
                        value.close()
                    raise TypeError("run_sync cannot resolve an awaitable Call")
            except BaseException as error:
                try:
                    current = program.throw(error)
                except StopIteration as done:
                    return cast(_ResultT, done.value)
            else:
                try:
                    current = program.send(value)
                except StopIteration as done:
                    return cast(_ResultT, done.value)
    finally:
        program.close()


async def run_async(program: Program[_ResultT]) -> _ResultT:
    """Run an effect program, awaiting calls when necessary."""
    try:
        try:
            current = next(program)
        except StopIteration as done:
            return cast(_ResultT, done.value)
        while True:
            try:
                value = current()
                if inspect.isawaitable(value):
                    value = await value
            except BaseException as error:
                try:
                    current = program.throw(error)
                except StopIteration as done:
                    return cast(_ResultT, done.value)
            else:
                try:
                    current = program.send(value)
                except StopIteration as done:
                    return cast(_ResultT, done.value)
    finally:
        program.close()
