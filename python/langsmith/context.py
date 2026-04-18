"""Context class for pulling and pushing non-prompt Hub repos (agents, skills, files)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Literal, Optional, Sequence

from langsmith import schemas as ls_schemas
from langsmith import utils as ls_utils

if TYPE_CHECKING:
    from langsmith.client import Client


_RepoType = Literal["agent", "skill", "file"]
_REPO_HANDLE_PATTERN = re.compile(r"^[a-z][a-z0-9-_]*$")
_PLATFORM_HUB = "/api/v1/platform/hub/repos"
_HUB = "/api/v1/hub/repos"


class Context:
    """Hub operations for non-prompt repos (agents, skills, files)."""

    def __init__(self, client: Client) -> None:
        """Initialize with a LangSmith client.

        Args:
            client: The LangSmith client instance.
        """
        self._client = client

    def pull_agent(
        self,
        identifier: str,
        *,
        version: Optional[str] = None,
    ) -> ls_schemas.AgentContext:
        """Pull an agent from Hub.

        Args:
            identifier: The identifier of the agent (owner/name:hash, owner/name, or name).
            version: The commit hash or tag to pull. Overrides the hash in the identifier.

        Returns:
            AgentContext: The agent snapshot.

        Raises:
            HTTPError: If the server request fails.
        """
        data = self._pull_directory(identifier, version=version)
        return ls_schemas.AgentContext.model_validate(data)

    def pull_skill(
        self,
        identifier: str,
        *,
        version: Optional[str] = None,
    ) -> ls_schemas.SkillContext:
        """Pull a skill from Hub.

        Args:
            identifier: The identifier of the skill.
            version: The commit hash or tag to pull.

        Returns:
            SkillContext: The skill snapshot.

        Raises:
            HTTPError: If the server request fails.
        """
        data = self._pull_directory(identifier, version=version)
        return ls_schemas.SkillContext.model_validate(data)

    def pull_file(
        self,
        identifier: str,
        *,
        version: Optional[str] = None,
    ) -> ls_schemas.FileContext:
        """Pull a file repo from Hub.

        Args:
            identifier: The identifier of the file repo.
            version: The commit hash or tag to pull.

        Returns:
            FileContext: The file repo snapshot.

        Raises:
            HTTPError: If the server request fails.
        """
        data = self._pull_directory(identifier, version=version)
        return ls_schemas.FileContext.model_validate(data)

    def push_agent(
        self,
        identifier: str,
        *,
        files: dict[str, Optional[ls_schemas.Entry]],
        parent_commit: Optional[str] = None,
        description: Optional[str] = None,
        readme: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
        is_public: Optional[bool] = None,
    ) -> str:
        """Push an agent to Hub.

        Creates the repo if it does not exist, updates metadata if provided,
        then creates a new commit with the given files.

        Args:
            identifier: The identifier of the agent.
            files: Map of path to entry. A value of None deletes the path.
            parent_commit: The parent commit hash (8-64 hex chars) for optimistic
                concurrency. When omitted, the server uses the current latest.
            description: Repo description to set on create or update.
            readme: Repo readme to set on create or update.
            tags: Repo tags to set on create or update.
            is_public: Whether the repo is public.

        Returns:
            str: The url of the agent commit.

        Raises:
            HTTPError: If the server request fails.
            LangSmithUserError: If validation fails.
        """
        return self._push_directory(
            identifier,
            "agent",
            files=files,
            parent_commit=parent_commit,
            description=description,
            readme=readme,
            tags=tags,
            is_public=is_public,
        )

    def push_skill(
        self,
        identifier: str,
        *,
        files: dict[str, Optional[ls_schemas.Entry]],
        parent_commit: Optional[str] = None,
        description: Optional[str] = None,
        readme: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
        is_public: Optional[bool] = None,
    ) -> str:
        """Push a skill to Hub.

        Args:
            identifier: The identifier of the skill.
            files: Map of path to entry. A value of None deletes the path.
            parent_commit: The parent commit hash for optimistic concurrency.
            description: Repo description to set on create or update.
            readme: Repo readme to set on create or update.
            tags: Repo tags to set on create or update.
            is_public: Whether the repo is public.

        Returns:
            str: The url of the skill commit.

        Raises:
            HTTPError: If the server request fails.
            LangSmithUserError: If validation fails.
        """
        return self._push_directory(
            identifier,
            "skill",
            files=files,
            parent_commit=parent_commit,
            description=description,
            readme=readme,
            tags=tags,
            is_public=is_public,
        )

    def push_file(
        self,
        identifier: str,
        *,
        files: dict[str, Optional[ls_schemas.FileEntry]],
        parent_commit: Optional[str] = None,
        description: Optional[str] = None,
        readme: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
        is_public: Optional[bool] = None,
    ) -> str:
        """Push a file repo to Hub.

        Args:
            identifier: The identifier of the file repo.
            files: Map of path to file entry. A value of None deletes the path.
            parent_commit: The parent commit hash for optimistic concurrency.
            description: Repo description to set on create or update.
            readme: Repo readme to set on create or update.
            tags: Repo tags to set on create or update.
            is_public: Whether the repo is public.

        Returns:
            str: The url of the file repo commit.

        Raises:
            HTTPError: If the server request fails.
            LangSmithUserError: If validation fails.
        """
        return self._push_directory(
            identifier,
            "file",
            files=files,
            parent_commit=parent_commit,
            description=description,
            readme=readme,
            tags=tags,
            is_public=is_public,
        )

    def delete_agent(self, identifier: str) -> None:
        """Delete an agent and all its owned child file repos.

        Args:
            identifier: The identifier of the agent.

        Raises:
            HTTPError: If the server request fails.
        """
        self._delete_directory(identifier)

    def delete_skill(self, identifier: str) -> None:
        """Delete a skill and all its owned child file repos.

        Args:
            identifier: The identifier of the skill.

        Raises:
            HTTPError: If the server request fails.
        """
        self._delete_directory(identifier)

    def delete_file(self, identifier: str) -> None:
        """Delete a file repo.

        Args:
            identifier: The identifier of the file repo.

        Raises:
            HTTPError: If the server request fails.
        """
        self._delete_directory(identifier)

    def list_agents(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        is_public: Optional[bool] = None,
        is_archived: Optional[bool] = False,
        query: Optional[str] = None,
    ) -> ls_schemas.ListPromptsResponse:
        """List agents with pagination.

        Args:
            limit: The maximum number to return.
            offset: The number to skip.
            is_public: Filter by public status.
            is_archived: Filter by archived status.
            query: Filter by a search query.

        Returns:
            ListPromptsResponse: A response containing the list of agents.
        """
        return self._list_repos(
            "agent",
            limit=limit,
            offset=offset,
            is_public=is_public,
            is_archived=is_archived,
            query=query,
        )

    def list_skills(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        is_public: Optional[bool] = None,
        is_archived: Optional[bool] = False,
        query: Optional[str] = None,
    ) -> ls_schemas.ListPromptsResponse:
        """List skills with pagination.

        Args:
            limit: The maximum number to return.
            offset: The number to skip.
            is_public: Filter by public status.
            is_archived: Filter by archived status.
            query: Filter by a search query.

        Returns:
            ListPromptsResponse: A response containing the list of skills.
        """
        return self._list_repos(
            "skill",
            limit=limit,
            offset=offset,
            is_public=is_public,
            is_archived=is_archived,
            query=query,
        )

    def list_files(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        is_public: Optional[bool] = None,
        is_archived: Optional[bool] = False,
        query: Optional[str] = None,
    ) -> ls_schemas.ListPromptsResponse:
        """List file repos with pagination.

        Args:
            limit: The maximum number to return.
            offset: The number to skip.
            is_public: Filter by public status.
            is_archived: Filter by archived status.
            query: Filter by a search query.

        Returns:
            ListPromptsResponse: A response containing the list of file repos.
        """
        return self._list_repos(
            "file",
            limit=limit,
            offset=offset,
            is_public=is_public,
            is_archived=is_archived,
            query=query,
        )

    def _pull_directory(
        self,
        identifier: str,
        *,
        version: Optional[str],
    ) -> dict[str, Any]:
        """Fetch the raw directory payload."""
        owner, name, commit = ls_utils.parse_prompt_identifier(identifier)
        target = version if version is not None else (
            commit if commit != "latest" else None
        )
        params: dict[str, Any] = {}
        if target:
            params["commit"] = target
        response = self._client.request_with_retries(
            "GET",
            f"{_PLATFORM_HUB}/{owner}/{name}/directories",
            params=params,
        )
        return response.json()

    def _push_directory(
        self,
        identifier: str,
        repo_type: _RepoType,
        *,
        files: dict[str, Any],
        parent_commit: Optional[str],
        description: Optional[str],
        readme: Optional[str],
        tags: Optional[Sequence[str]],
        is_public: Optional[bool],
    ) -> str:
        """Create a directory commit, creating the repo if it does not exist."""
        if len(files) > ls_schemas.MAX_CONTEXT_ENTRIES:
            raise ls_utils.LangSmithUserError(
                f"Too many files ({len(files)}); max is {ls_schemas.MAX_CONTEXT_ENTRIES}."
            )
        if parent_commit is not None and not (8 <= len(parent_commit) <= 64):
            raise ls_utils.LangSmithUserError(
                "parent_commit must be 8-64 characters."
            )

        owner, name, _ = ls_utils.parse_prompt_identifier(identifier)
        if not self._client._current_tenant_is_owner(owner):
            raise self._client._owner_conflict_error(f"push {repo_type}", owner)

        if self._repo_exists(owner, name):
            if any(v is not None for v in (description, readme, tags, is_public)):
                self._update_repo_metadata(
                    owner,
                    name,
                    description=description,
                    readme=readme,
                    tags=tags,
                    is_public=is_public,
                )
        else:
            if not _REPO_HANDLE_PATTERN.match(name):
                raise ls_utils.LangSmithUserError(
                    f"Invalid repo_handle {name!r}: must match {_REPO_HANDLE_PATTERN.pattern}."
                )
            self._create_repo(
                name,
                repo_type,
                description=description,
                readme=readme,
                tags=tags,
                is_public=bool(is_public),
            )

        request_files: dict[str, Optional[dict[str, Any]]] = {}
        for path, entry in files.items():
            if entry is None:
                request_files[path] = None
            else:
                request_files[path] = entry.model_dump(exclude_none=True)

        body: dict[str, Any] = {"files": request_files}
        if parent_commit is not None:
            body["parent_commit"] = parent_commit

        response = self._client.request_with_retries(
            "POST",
            f"{_PLATFORM_HUB}/{owner}/{name}/directories/commits",
            json=body,
        )
        commit_hash = response.json()["commit"]["commit_hash"]
        return self._get_context_url(owner, name, commit_hash)

    def _delete_directory(self, identifier: str) -> None:
        """Delete a directory repo."""
        owner, name, _ = ls_utils.parse_prompt_identifier(identifier)
        if not self._client._current_tenant_is_owner(owner):
            raise self._client._owner_conflict_error("delete", owner)
        self._client.request_with_retries(
            "DELETE",
            f"{_PLATFORM_HUB}/{owner}/{name}/directories",
        )

    def _list_repos(
        self,
        repo_type: _RepoType,
        *,
        limit: int,
        offset: int,
        is_public: Optional[bool],
        is_archived: Optional[bool],
        query: Optional[str],
    ) -> ls_schemas.ListPromptsResponse:
        """List repos filtered by type."""
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "repo_type": repo_type,
            "is_archived": "true" if is_archived else "false",
        }
        if is_public is not None:
            params["is_public"] = "true" if is_public else "false"
        if query:
            params["query"] = query
            params["match_prefix"] = "true"
        response = self._client.request_with_retries("GET", _HUB, params=params)
        return ls_schemas.ListPromptsResponse(**response.json())

    def _repo_exists(self, owner: str, name: str) -> bool:
        """Check if a repo exists."""
        try:
            self._client.request_with_retries("GET", f"{_HUB}/{owner}/{name}")
            return True
        except ls_utils.LangSmithNotFoundError:
            return False

    def _create_repo(
        self,
        name: str,
        repo_type: _RepoType,
        *,
        description: Optional[str],
        readme: Optional[str],
        tags: Optional[Sequence[str]],
        is_public: bool,
    ) -> None:
        """Create a new repo of the given type."""
        body: dict[str, Any] = {
            "repo_handle": name,
            "repo_type": repo_type,
            "is_public": is_public,
        }
        if description is not None:
            body["description"] = description
        if readme is not None:
            body["readme"] = readme
        if tags is not None:
            body["tags"] = list(tags)
        self._client.request_with_retries("POST", f"{_PLATFORM_HUB}/", json=body)

    def _update_repo_metadata(
        self,
        owner: str,
        name: str,
        *,
        description: Optional[str],
        readme: Optional[str],
        tags: Optional[Sequence[str]],
        is_public: Optional[bool],
    ) -> None:
        """Patch repo metadata fields that were explicitly provided."""
        body: dict[str, Any] = {}
        if description is not None:
            body["description"] = description
        if readme is not None:
            body["readme"] = readme
        if tags is not None:
            body["tags"] = list(tags)
        if is_public is not None:
            body["is_public"] = is_public
        if body:
            self._client.request_with_retries(
                "PATCH", f"{_HUB}/{owner}/{name}", json=body
            )

    def _get_context_url(self, owner: str, name: str, commit_hash: str) -> str:
        """Build a URL for a pushed context commit."""
        return f"{self._client._host_url}/hub/{owner}/{name}:{commit_hash[:8]}"
