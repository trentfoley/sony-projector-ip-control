"""Typed exceptions for ADCP protocol errors."""


class ADCPError(Exception):
    """Base exception for all ADCP errors."""


class AuthError(ADCPError):
    """ADCP authentication failed (err_auth)."""


class CommandError(ADCPError):
    """Unknown ADCP command (err_cmd)."""


class CommandValueError(ADCPError):
    """Invalid parameter value for ADCP command (err_val)."""


class InactiveError(ADCPError):
    """Projector ADCP service inactive, likely in deep standby (err_inactive)."""


class ConnectionError(ADCPError):
    """TCP connection to projector failed (connect/read timeout, refused)."""


class ConfigError(Exception):
    """Configuration file loading or validation error."""
