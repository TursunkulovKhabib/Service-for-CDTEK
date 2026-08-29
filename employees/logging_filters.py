import logging
import re

MASK = "***"
SENSITIVE_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key)\b(\s*[=:]\s*)(\S+)"
)


class MaskSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        masked = SENSITIVE_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", message)
        if masked != message:
            record.msg = masked
            record.args = ()
        return True
