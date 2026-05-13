# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from ...._models import BaseModel

__all__ = ["EncryptedRetrieveResponse"]


class EncryptedRetrieveResponse(BaseModel):
    encrypted_secrets: str

    tenant_id: Optional[str] = None
