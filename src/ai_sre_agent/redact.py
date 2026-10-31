"""Masks secrets and personal data before anything is sent to the LLM.

Tokens, passwords and private keys are replaced outright. IP addresses and e-mail addresses get stable
placeholders (<ip-1>, <email-2>) within one investigation, so the model can still tell that two results
mention the same pod IP without seeing it.
"""

import ipaddress
import re

_SECRETS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "<private-key>"),
    (re.compile(r"\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}"), "<jwt>"),
    (re.compile(r"(?i)\bbearer\s+[\w.~+/-]{8,}=*"), "Bearer <token>"),
    (re.compile(r"\bxox[abposr]-[\w-]{10,}"), "<slack-token>"),
    (re.compile(r"\bsk-[\w-]{16,}"), "<api-key>"),
    (re.compile(r"\bgh[pousr]_\w{20,}"), "<github-token>"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "<aws-key>"),
    # scheme://user:password@host
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^\s/:@]+:[^\s/@]+@"), r"\1<credentials>@"),
    # password=..., "token": "...", API_KEY: ...
    (
        re.compile(
            r"(?i)(\b[\w-]*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)[\w-]*\"?\s*[:=]\s*\"?)"
            r"(?!<|\[redacted\])[^\s\",;}]+"
        ),
        r"\1<redacted>",
    ),
]
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_IPV4 = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?![\w.]|\.\d)")


class Redactor:
    """One per investigation: the placeholders stay consistent across all the text it masks."""

    def __init__(self) -> None:
        self._ips: dict[str, str] = {}
        self._emails: dict[str, str] = {}

    def __call__(self, text: str) -> str:
        for pattern, replacement in _SECRETS:
            text = pattern.sub(replacement, text)
        text = _EMAIL.sub(lambda m: self._placeholder(self._emails, m.group(0), "email"), text)
        return _IPV4.sub(self._ip, text)

    def _ip(self, match: re.Match[str]) -> str:
        try:
            ipaddress.IPv4Address(match.group(1))
        except ValueError:  # 999.1.2.3, a version number and such: leave it
            return match.group(0)
        return self._placeholder(self._ips, match.group(1), "ip")

    @staticmethod
    def _placeholder(seen: dict[str, str], value: str, kind: str) -> str:
        if value not in seen:
            seen[value] = f"<{kind}-{len(seen) + 1}>"
        return seen[value]
