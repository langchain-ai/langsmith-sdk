"""Use HTTPX2 for tests that import the legacy HTTPX module name."""

import httpx2

httpx2.alias_httpx()
