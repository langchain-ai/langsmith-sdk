# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional

from .._models import BaseModel

__all__ = ["InfoListResponse", "BatchIngestConfig", "CustomerInfo", "SDKVersions"]


class BatchIngestConfig(BaseModel):
    scale_down_nempty_trigger: Optional[int] = None

    scale_up_nthreads_limit: Optional[int] = None

    scale_up_qsize_trigger: Optional[int] = None

    size_limit: Optional[int] = None

    size_limit_bytes: Optional[int] = None

    use_multipart_endpoint: Optional[bool] = None


class CustomerInfo(BaseModel):
    customer_id: Optional[str] = None

    customer_name: Optional[str] = None


class SDKVersions(BaseModel):
    max_go_sdk_version: Optional[str] = None

    max_java_sdk_version: Optional[str] = None

    max_js_sdk_version: Optional[str] = None

    max_python_sdk_version: Optional[str] = None


class InfoListResponse(BaseModel):
    batch_ingest_config: Optional[BatchIngestConfig] = None

    customer_info: Optional[CustomerInfo] = None

    git_sha: Optional[str] = None

    instance_flags: Optional[Dict[str, object]] = None

    license_expiration_time: Optional[str] = None

    sdk_versions: Optional[SDKVersions] = None

    version: Optional[str] = None
