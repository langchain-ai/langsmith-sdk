"""Tests for sandbox exceptions."""

from langsmith.sandbox import (
    QuotaExceededError,
    ResourceNameConflictError,
    ResourceNotFoundError,
    ResourceTimeoutError,
    SandboxClientError,
    SandboxCreationError,
    SandboxOperationError,
    ValidationError,
)
from langsmith.utils import LangSmithError


class TestExceptionHierarchy:
    """Test that sandbox exceptions extend LangSmithError."""

    def test_sandbox_client_error_extends_langsmith_error(self):
        """Test that SandboxClientError extends LangSmithError."""
        assert issubclass(SandboxClientError, LangSmithError)

    def test_sandbox_client_error_can_be_raised(self):
        """Test that SandboxClientError can be raised and caught."""
        try:
            raise SandboxClientError("test error")
        except LangSmithError as e:
            assert str(e) == "test error"


class TestResourceTimeoutError:
    """Tests for ResourceTimeoutError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = ResourceTimeoutError("Timeout waiting for sandbox")
        assert str(error) == "Timeout waiting for sandbox"
        assert error.last_status is None
        assert error.resource_type is None

    def test_with_last_status(self):
        """Test error with last_status."""
        error = ResourceTimeoutError(
            "Timeout waiting for sandbox",
            resource_type="sandbox",
            last_status="Pending",
        )
        assert "Timeout waiting for sandbox" in str(error)
        assert "last_status: Pending" in str(error)
        assert error.last_status == "Pending"
        assert error.resource_type == "sandbox"


class TestResourceNotFoundError:
    """Tests for ResourceNotFoundError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = ResourceNotFoundError("Resource not found")
        assert str(error) == "Resource not found"
        assert error.resource_type is None

    def test_with_resource_type(self):
        """Test error with resource_type."""
        error = ResourceNotFoundError("Template not found", resource_type="template")
        assert error.resource_type == "template"


class TestValidationError:
    """Tests for ValidationError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = ValidationError("Invalid CPU value")
        assert str(error) == "Invalid CPU value"
        assert error.field is None
        assert error.details == []

    def test_with_field_and_details(self):
        """Test error with field and details."""
        details = [{"loc": ["body", "cpu"], "msg": "value too high"}]
        error = ValidationError(
            "Invalid CPU value",
            field="cpu",
            details=details,
        )
        assert error.field == "cpu"
        assert error.details == details


class TestQuotaExceededError:
    """Tests for QuotaExceededError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = QuotaExceededError("Quota exceeded")
        assert str(error) == "Quota exceeded"
        assert error.quota_type is None

    def test_with_quota_type(self):
        """Test error with quota_type."""
        error = QuotaExceededError("Quota exceeded", quota_type="sandbox_count")
        assert error.quota_type == "sandbox_count"


class TestSandboxCreationError:
    """Tests for SandboxCreationError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = SandboxCreationError("Failed to create sandbox")
        assert str(error) == "Failed to create sandbox"
        assert error.error_type is None

    def test_with_error_type(self):
        """Test error with error_type."""
        error = SandboxCreationError("Image pull failed", error_type="ImagePull")
        assert "[ImagePull]" in str(error)
        assert error.error_type == "ImagePull"


class TestSandboxOperationError:
    """Tests for SandboxOperationError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = SandboxOperationError("Command failed")
        assert str(error) == "Command failed"
        assert error.error_type is None

    def test_with_error_type(self):
        """Test error with error_type."""
        error = SandboxOperationError("Write failed", error_type="WriteError")
        assert "[WriteError]" in str(error)
        assert error.error_type == "WriteError"

    def test_with_operation(self):
        """Test error with operation."""
        error = SandboxOperationError(
            "Write failed", operation="write", error_type="WriteError"
        )
        assert error.operation == "write"


class TestResourceNameConflictError:
    """Tests for ResourceNameConflictError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = ResourceNameConflictError("Name already exists")
        assert str(error) == "Name already exists"
        assert error.resource_type is None

    def test_with_resource_type(self):
        """Test error with resource_type."""
        error = ResourceNameConflictError("Name already exists", resource_type="volume")
        assert error.resource_type == "volume"
