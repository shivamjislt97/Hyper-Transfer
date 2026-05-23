"""
Detects MEGA quota exceeded signals from megatools output.
"""

QUOTA_SIGNALS = (
    "overquota",
    "quotaexceeded",
    "transferquota",
    "quota exceeded",
    "err: api",
    "-18",           # MEGA API error code for quota exceeded
)


def is_quota_exceeded(output: str) -> bool:
    """
    Returns True if the output string contains any quota-exceeded indicator.
    Case-insensitive, whitespace-tolerant.
    """
    normalized = output.lower().replace(" ", "")
    for signal in QUOTA_SIGNALS:
        if signal.replace(" ", "") in normalized:
            return True
    return False
