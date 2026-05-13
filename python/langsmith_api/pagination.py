# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Any, List, Type, Generic, Mapping, TypeVar, Optional, cast
from typing_extensions import override

from httpx import Response

from ._utils import is_mapping
from ._models import BaseModel
from ._base_client import BasePage, PageInfo, BaseSyncPage, BaseAsyncPage

__all__ = [
    "SyncOffsetPaginationTopLevelArray",
    "AsyncOffsetPaginationTopLevelArray",
    "SyncOffsetPaginationRepos",
    "AsyncOffsetPaginationRepos",
    "SyncOffsetPaginationCommits",
    "AsyncOffsetPaginationCommits",
    "SyncOffsetPaginationInsightsClusteringJobs",
    "AsyncOffsetPaginationInsightsClusteringJobs",
    "CursorPaginationCursors",
    "SyncCursorPagination",
    "AsyncCursorPagination",
    "SyncItemsCursorPostPagination",
    "AsyncItemsCursorPostPagination",
    "SyncItemsCursorGetPagination",
    "AsyncItemsCursorGetPagination",
]

_BaseModelT = TypeVar("_BaseModelT", bound=BaseModel)

_T = TypeVar("_T")


class SyncOffsetPaginationTopLevelArray(BaseSyncPage[_T], BasePage[_T], Generic[_T]):
    items: List[_T]

    @override
    def _get_page_items(self) -> List[_T]:
        items = self.items
        if not items:
            return []
        return items

    @override
    def next_page_info(self) -> Optional[PageInfo]:
        offset = self._options.params.get("offset") or 0
        if not isinstance(offset, int):
            raise ValueError(f'Expected "offset" param to be an integer but got {offset}')

        length = len(self._get_page_items())
        current_count = offset + length

        return PageInfo(params={"offset": current_count})

    @classmethod
    def build(cls: Type[_BaseModelT], *, response: Response, data: object) -> _BaseModelT:  # noqa: ARG003
        return cls.construct(
            None,
            **{
                **(cast(Mapping[str, Any], data) if is_mapping(data) else {"items": data}),
            },
        )


class AsyncOffsetPaginationTopLevelArray(BaseAsyncPage[_T], BasePage[_T], Generic[_T]):
    items: List[_T]

    @override
    def _get_page_items(self) -> List[_T]:
        items = self.items
        if not items:
            return []
        return items

    @override
    def next_page_info(self) -> Optional[PageInfo]:
        offset = self._options.params.get("offset") or 0
        if not isinstance(offset, int):
            raise ValueError(f'Expected "offset" param to be an integer but got {offset}')

        length = len(self._get_page_items())
        current_count = offset + length

        return PageInfo(params={"offset": current_count})

    @classmethod
    def build(cls: Type[_BaseModelT], *, response: Response, data: object) -> _BaseModelT:  # noqa: ARG003
        return cls.construct(
            None,
            **{
                **(cast(Mapping[str, Any], data) if is_mapping(data) else {"items": data}),
            },
        )


class SyncOffsetPaginationRepos(BaseSyncPage[_T], BasePage[_T], Generic[_T]):
    repos: List[_T]
    total: Optional[int] = None

    @override
    def _get_page_items(self) -> List[_T]:
        repos = self.repos
        if not repos:
            return []
        return repos

    @override
    def next_page_info(self) -> Optional[PageInfo]:
        offset = self._options.params.get("offset") or 0
        if not isinstance(offset, int):
            raise ValueError(f'Expected "offset" param to be an integer but got {offset}')

        length = len(self._get_page_items())
        current_count = offset + length

        return PageInfo(params={"offset": current_count})


class AsyncOffsetPaginationRepos(BaseAsyncPage[_T], BasePage[_T], Generic[_T]):
    repos: List[_T]
    total: Optional[int] = None

    @override
    def _get_page_items(self) -> List[_T]:
        repos = self.repos
        if not repos:
            return []
        return repos

    @override
    def next_page_info(self) -> Optional[PageInfo]:
        offset = self._options.params.get("offset") or 0
        if not isinstance(offset, int):
            raise ValueError(f'Expected "offset" param to be an integer but got {offset}')

        length = len(self._get_page_items())
        current_count = offset + length

        return PageInfo(params={"offset": current_count})


class SyncOffsetPaginationCommits(BaseSyncPage[_T], BasePage[_T], Generic[_T]):
    commits: List[_T]
    total: Optional[int] = None

    @override
    def _get_page_items(self) -> List[_T]:
        commits = self.commits
        if not commits:
            return []
        return commits

    @override
    def next_page_info(self) -> Optional[PageInfo]:
        offset = self._options.params.get("offset") or 0
        if not isinstance(offset, int):
            raise ValueError(f'Expected "offset" param to be an integer but got {offset}')

        length = len(self._get_page_items())
        current_count = offset + length

        return PageInfo(params={"offset": current_count})


class AsyncOffsetPaginationCommits(BaseAsyncPage[_T], BasePage[_T], Generic[_T]):
    commits: List[_T]
    total: Optional[int] = None

    @override
    def _get_page_items(self) -> List[_T]:
        commits = self.commits
        if not commits:
            return []
        return commits

    @override
    def next_page_info(self) -> Optional[PageInfo]:
        offset = self._options.params.get("offset") or 0
        if not isinstance(offset, int):
            raise ValueError(f'Expected "offset" param to be an integer but got {offset}')

        length = len(self._get_page_items())
        current_count = offset + length

        return PageInfo(params={"offset": current_count})


class SyncOffsetPaginationInsightsClusteringJobs(BaseSyncPage[_T], BasePage[_T], Generic[_T]):
    clustering_jobs: List[_T]

    @override
    def _get_page_items(self) -> List[_T]:
        clustering_jobs = self.clustering_jobs
        if not clustering_jobs:
            return []
        return clustering_jobs

    @override
    def next_page_info(self) -> Optional[PageInfo]:
        offset = self._options.params.get("offset") or 0
        if not isinstance(offset, int):
            raise ValueError(f'Expected "offset" param to be an integer but got {offset}')

        length = len(self._get_page_items())
        current_count = offset + length

        return PageInfo(params={"offset": current_count})


class AsyncOffsetPaginationInsightsClusteringJobs(BaseAsyncPage[_T], BasePage[_T], Generic[_T]):
    clustering_jobs: List[_T]

    @override
    def _get_page_items(self) -> List[_T]:
        clustering_jobs = self.clustering_jobs
        if not clustering_jobs:
            return []
        return clustering_jobs

    @override
    def next_page_info(self) -> Optional[PageInfo]:
        offset = self._options.params.get("offset") or 0
        if not isinstance(offset, int):
            raise ValueError(f'Expected "offset" param to be an integer but got {offset}')

        length = len(self._get_page_items())
        current_count = offset + length

        return PageInfo(params={"offset": current_count})


class CursorPaginationCursors(BaseModel):
    next: Optional[str] = None


class SyncCursorPagination(BaseSyncPage[_T], BasePage[_T], Generic[_T]):
    runs: List[_T]
    cursors: Optional[CursorPaginationCursors] = None

    @override
    def _get_page_items(self) -> List[_T]:
        runs = self.runs
        if not runs:
            return []
        return runs

    @override
    def next_page_info(self) -> Optional[PageInfo]:
        next = None
        if self.cursors is not None:
            if self.cursors.next is not None:
                next = self.cursors.next
        if not next:
            return None

        return PageInfo(json={"cursor": next})


class AsyncCursorPagination(BaseAsyncPage[_T], BasePage[_T], Generic[_T]):
    runs: List[_T]
    cursors: Optional[CursorPaginationCursors] = None

    @override
    def _get_page_items(self) -> List[_T]:
        runs = self.runs
        if not runs:
            return []
        return runs

    @override
    def next_page_info(self) -> Optional[PageInfo]:
        next = None
        if self.cursors is not None:
            if self.cursors.next is not None:
                next = self.cursors.next
        if not next:
            return None

        return PageInfo(json={"cursor": next})


class SyncItemsCursorPostPagination(BaseSyncPage[_T], BasePage[_T], Generic[_T]):
    items: List[_T]
    next_cursor: Optional[str] = None

    @override
    def _get_page_items(self) -> List[_T]:
        items = self.items
        if not items:
            return []
        return items

    @override
    def next_page_info(self) -> Optional[PageInfo]:
        next_cursor = self.next_cursor
        if not next_cursor:
            return None

        return PageInfo(json={"cursor": next_cursor})


class AsyncItemsCursorPostPagination(BaseAsyncPage[_T], BasePage[_T], Generic[_T]):
    items: List[_T]
    next_cursor: Optional[str] = None

    @override
    def _get_page_items(self) -> List[_T]:
        items = self.items
        if not items:
            return []
        return items

    @override
    def next_page_info(self) -> Optional[PageInfo]:
        next_cursor = self.next_cursor
        if not next_cursor:
            return None

        return PageInfo(json={"cursor": next_cursor})


class SyncItemsCursorGetPagination(BaseSyncPage[_T], BasePage[_T], Generic[_T]):
    items: List[_T]
    next_cursor: Optional[str] = None

    @override
    def _get_page_items(self) -> List[_T]:
        items = self.items
        if not items:
            return []
        return items

    @override
    def next_page_info(self) -> Optional[PageInfo]:
        next_cursor = self.next_cursor
        if not next_cursor:
            return None

        return PageInfo(params={"cursor": next_cursor})


class AsyncItemsCursorGetPagination(BaseAsyncPage[_T], BasePage[_T], Generic[_T]):
    items: List[_T]
    next_cursor: Optional[str] = None

    @override
    def _get_page_items(self) -> List[_T]:
        items = self.items
        if not items:
            return []
        return items

    @override
    def next_page_info(self) -> Optional[PageInfo]:
        next_cursor = self.next_cursor
        if not next_cursor:
            return None

        return PageInfo(params={"cursor": next_cursor})
