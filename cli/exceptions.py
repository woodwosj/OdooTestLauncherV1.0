"""Custom exception hierarchy for the launcher."""


class LauncherError(Exception):
    """Base exception for launcher failures."""


class ManifestError(LauncherError):
    """Raised when manifest parsing or validation fails."""


class ValidationError(LauncherError):
    """Raised when user input fails validation."""


class DockerError(LauncherError):
    """Raised when Docker commands return non-zero exit codes."""


class SeedError(LauncherError):
    """Raised when seed execution fails."""


class EnterpriseError(LauncherError):
    """Raised when enterprise licence handling goes wrong."""
