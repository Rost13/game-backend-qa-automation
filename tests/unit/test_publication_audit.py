from __future__ import annotations

import subprocess
from pathlib import Path

from qa_automation.publication_audit import (
    audit_paths,
    collect_publishable_paths,
    format_findings,
)


def test_audit_detects_jwt_without_exposing_its_value(tmp_path: Path) -> None:
    encoded_header = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    encoded_payload = "eyJzdWIiOiJwdWJsaWNhdGlvbi10ZXN0LXVzZXIifQ"
    signature = "test_signature_that_is_long_enough_for_detection"
    token = ".".join((encoded_header, encoded_payload, signature))
    candidate = tmp_path / "settings.txt"
    candidate.write_text(f"API_TOKEN={token}\n", encoding="utf-8")

    findings = audit_paths([candidate], root=tmp_path)
    report = format_findings(findings, root=tmp_path)

    assert [(finding.rule_id, finding.line_number) for finding in findings] == [("JWT", 1)]
    assert "settings.txt:1: JWT" in report
    assert token not in report


def test_audit_detects_private_key_and_credentialed_database_url(tmp_path: Path) -> None:
    private_key_header = "-----BEGIN " + "PRIVATE KEY-----"
    database_url = "postgresql://" + "qa_user:nonpublic-password" + "@db.example.test/game"
    candidate = tmp_path / "credentials.txt"
    candidate.write_text(
        f"{private_key_header}\nDATABASE_URL={database_url}\n",
        encoding="utf-8",
    )

    findings = audit_paths([candidate], root=tmp_path)

    assert [(finding.rule_id, finding.line_number) for finding in findings] == [
        ("PRIVATE_KEY", 1),
        ("CREDENTIALED_URL", 2),
    ]


def test_audit_detects_forbidden_term_without_echoing_it(tmp_path: Path) -> None:
    forbidden_host = "private" + ".example.internal"
    candidate = tmp_path / "documentation.md"
    candidate.write_text(f"Endpoint: https://{forbidden_host}/api\n", encoding="utf-8")

    findings = audit_paths(
        [candidate],
        root=tmp_path,
        forbidden_terms=[forbidden_host],
    )
    report = format_findings(findings, root=tmp_path)

    assert [(finding.rule_id, finding.line_number) for finding in findings] == [
        ("FORBIDDEN_TERM", 1),
        ("UNAPPROVED_URL", 1),
    ]
    assert forbidden_host not in report


def test_publishable_paths_follow_git_ignore_rules(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / ".env").write_text("API_TOKEN=local-only\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("API_TOKEN=\n", encoding="utf-8")

    paths = collect_publishable_paths(tmp_path)
    relative_paths = {path.relative_to(tmp_path).as_posix() for path in paths}

    assert ".env" not in relative_paths
    assert ".env.example" in relative_paths
    assert ".gitignore" in relative_paths


def test_audit_rejects_unapproved_absolute_url_without_manual_denylist(
    tmp_path: Path,
) -> None:
    private_host = "private" + ".example.internal"
    candidate = tmp_path / "configuration.md"
    candidate.write_text(f"Endpoint: https://{private_host}/api\n", encoding="utf-8")

    findings = audit_paths([candidate], root=tmp_path)

    assert [(finding.rule_id, finding.line_number) for finding in findings] == [
        ("UNAPPROVED_URL", 1)
    ]
