"""LangChain+ Client."""


from importlib import metadata

from langchainplus_sdk.client import LangChainPlusClient
from langchainplus_sdk.run_trees import RunTree

try:
    __version__ = metadata.version(__package__)
except metadata.PackageNotFoundError:
    # Case where package metadata is not available.
    __version__ = ""

__all__ = ["LangChainPlusClient", "RunTree", "__version__"]
