"""Provide utilities for managing caching in LangSmith.

Includes a CacheManager class that handles the lifecycle of caching
operations, allowing for easy setup and teardown of caching contexts.
"""

import pathlib
from typing import Optional, Sequence, Union

from langsmith import utils


class CacheManager:
    """Manage caching operations for LangSmith.

    Provides methods to start and stop caching, and can be used
    as a context manager for automatic cache management.

    Attributes:
        path (Optional[Union[str, pathlib.Path]]): The path to the cache file.
        ignore_hosts (Optional[Sequence[str]]): A list of hosts to ignore in caching.
        context_manager: The context manager for caching operations.
        context: The context object for the current caching session.
    """

    def __init__(
        self,
        path: Optional[Union[str, pathlib.Path]],
        ignore_hosts: Optional[Sequence[str]] = None,
    ):
        """Initialize the CacheManager.

        Args:
            path: The path to the cache file.
            ignore_hosts: A list of hosts to ignore in caching.
        """
        self.path = path
        self.ignore_hosts = ignore_hosts
        self.context_manager = None
        self.context = None

    def start_caching(self):
        """Start the caching session.

        Returns:
            self: The CacheManager instance.

        Raises:
            RuntimeError: If caching is already started.
        """
        if self.context is not None:
            raise RuntimeError("Caching is already started")

        self.context_manager = utils.with_optional_cache(self.path, self.ignore_hosts)
        if self.context_manager:
            self.context = self.context_manager.__enter__()
        return self

    def close(self):
        """Close the current caching session.

        Raises:
            RuntimeError: If caching is not started.
        """
        if self.context_manager is not None:
            self.context_manager.__exit__(None, None, None)
            if self.context is None:
                raise RuntimeError("Caching is not started")
        self.context = None
        self.context_manager = None

    def __enter__(self):
        """Enter the context manager, starting the caching session.

        Returns:
            self: The CacheManager instance with caching started.
        """
        return self.start_caching()

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the context manager, closing the caching session.

        Args:
            exc_type: The type of the exception that caused the context to be exited.
            exc_value: The instance of the exception.
            traceback: A traceback object encoding the stack trace.
        """
        self.close()
