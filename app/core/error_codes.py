"""Business codes shared with the existing Deckwise Web contract."""

from enum import IntEnum


class ErrorCode(IntEnum):
    SUCCESS = 0
    PARAMS_ERROR = 40000
    PARAM_VALIDATION_FAILED = 40010
    TOKEN_INVALID = 40102
    FORBIDDEN = 40300
    NOT_FOUND = 40400
    REVISION_CONFLICT = 40903
    SYSTEM_ERROR = 50000
    SYSTEM_BUSY = 50300
    EXTERNAL_SERVICE_ERROR = 50400
