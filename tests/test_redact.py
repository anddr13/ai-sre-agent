import pytest

from ai_sre_agent.redact import Redactor


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        ("Authorization: Bearer abcdef1234567890", "abcdef1234567890"),
        ("token xoxb-1234567890-abcdefghij", "xoxb-1234567890-abcdefghij"),
        ("key sk-or-v1-0123456789abcdef0123", "sk-or-v1-0123456789abcdef0123"),
        ("gh token ghp_abcdefghijklmnopqrstuvwxyz0123", "ghp_abcdefghijklmnopqrstuvwxyz0123"),
        ("aws AKIAABCDEFGHIJKLMNOP", "AKIAABCDEFGHIJKLMNOP"),
        ("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N", "dozjgNryP4J3jVmNHl0w5N"),
        ("postgres://voting:s3cr3t@voting-pg-rw:5432/voting", "s3cr3t"),
        ("PGPASSWORD=hunter2 node src/index.js", "hunter2"),
        ('{"api_key": "abc123xyz", "x": 1}', "abc123xyz"),
        ("client_secret: verysecretvalue", "verysecretvalue"),
        ("-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----", "MIIEow"),
    ],
)
def test_secrets_are_masked(text: str, secret: str) -> None:
    assert secret not in Redactor()(text)


def test_ips_and_emails_get_stable_placeholders() -> None:
    redact = Redactor()
    first = redact("pod 10.244.0.36:9187 and 10.244.0.41, owner anddr13@example.com")
    second = redact("again 10.244.0.41 and anddr13@example.com")
    assert first == "pod <ip-1>:9187 and <ip-2>, owner <email-1>"
    assert second == "again <ip-2> and <email-1>"


@pytest.mark.parametrize(
    "text",
    [
        "image ghcr.io/anddr13/voting-worker:74f671ba05f3e8001e778e47ed8201e95d4323e9",
        "postgresql 18.6, kafka 4.3.1, chart 92.16.1",
        "2026-10-31T10:34:40Z",
        "max_connections 100, tokens used 1234",
        "Reason: ImagePullBackOff",
    ],
)
def test_ordinary_text_is_kept(text: str) -> None:
    assert Redactor()(text) == text


def test_already_redacted_values_stay_readable() -> None:
    assert Redactor()('{"name": "API_TOKEN", "value": "[redacted]"}') == '{"name": "API_TOKEN", "value": "[redacted]"}'
