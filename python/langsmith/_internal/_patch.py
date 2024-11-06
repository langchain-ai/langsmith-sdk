# mypy: disable-error-code="import-untyped"
import functools

import six  # noqa
from urllib3 import __version__ as urllib3version  # noqa
from urllib3 import connection  # noqa


# Copied from https://github.com/urllib3/urllib3/blob/1c994dfc8c5d5ecaee8ed3eb585d4785f5febf6e/src/urllib3/connection.py#L231
def request(self, method, url, body=None, headers=None):
    # Update the inner socket's timeout value to send the request.
    # This only triggers if the connection is re-used.
    if getattr(self, "sock", None) is not None:
        self.sock.settimeout(self.timeout)

    if headers is None:
        headers = {}
    else:
        # Avoid modifying the headers passed into .request()
        headers = headers.copy()
    if "user-agent" not in (six.ensure_str(k.lower()) for k in headers):
        headers["User-Agent"] = connection._get_default_user_agent()
    # Use the parent class's request method
    return self._parent_request(method, url, body=body, headers=headers)


_PATCHED = False


def patch_urllib3():
    global _PATCHED
    if _PATCHED:
        return
    from packaging import version

    if version.parse(urllib3version) >= version.parse("2.0"):
        _PATCHED = True
        return

    # Lookup the parent class and its request method
    parent_class = connection.HTTPConnection.__bases__[0]
    parent_request = parent_class.request

    # Create a new request method with the parent's request method bound to self
    def new_request(self, *args, **kwargs):
        self._parent_request = functools.partial(parent_request, self)
        return request(self, *args, **kwargs)

    connection.HTTPConnection.request = new_request
    _PATCHED = True
