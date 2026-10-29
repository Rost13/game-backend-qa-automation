from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    path: Path
    line_number: int


_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "UNAPPROVED_URL",
        re.compile(
            r"\bhttps?://(?!(?:example\.test|localhost|127\.0\.0\.1)"
            r"(?::\d+)?(?:/|$))[A-Za-z0-9.-]+",
            re.IGNORECASE,
        ),
    ),
    (
        "JWT",
        re.compile(
            r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,}\."
            r"[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?![A-Za-z0-9_-])"
        ),
    ),
    (
        "GITHUB_TOKEN",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    ),
    ("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("GOOGLE_API_KEY", re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b")),
    ("DIGITALOCEAN_TOKEN", re.compile(r"\bdop_v1_[A-Za-z0-9]{40,}\b")),
    ("OPENAI_API_KEY", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b")),
    ("SLACK_TOKEN", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("STRIPE_SECRET_KEY", re.compile(r"\bsk_live_[A-Za-z0-9]{20,}\b")),
    (
        "PRIVATE_KEY",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    (
        "CREDENTIALED_URL",
        re.compile(
            r"\b(?:https?|postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://"
            r"[^\s/:@]+:[^\s/@]+@",
            re.IGNORECASE,
        ),
    ),
    (
        "BEARER_TOKEN",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{24,}", re.IGNORECASE),
    ),
    (
        "KUBECONFIG_CREDENTIAL",
        re.compile(r"^\s*(?:client-key-data|client-certificate-data)\s*:\s*\S+"),
    ),
    (
        "PRIVATE_IPV4",
        re.compile(
            r"(?<!\d)(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
            r"192\.168\.\d{1,3}\.\d{1,3})(?!\d)"
        ),
    ),
)


def collect_publishable_paths(root: Path) -> list[Path]:
    normalized_root = root.resolve()
    command = [
        "git",
        "-c",
        f"safe.directory={normalized_root.as_posix()}",
        "-C",
        str(normalized_root),
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "-z",
    ]
    result = subprocess.run(command, check=True, capture_output=True)
    relative_paths = (
        Path(value.decode("utf-8", errors="surrogateescape"))
        for value in result.stdout.split(b"\0")
        if value
    )
    return sorted(
        (
            normalized_root / relative_path
            for relative_path in relative_paths
            if (normalized_root / relative_path).is_file()
        ),
        key=lambda path: path.as_posix(),
    )


def audit_paths(
    paths: Iterable[Path],
    *,
    root: Path,
    forbidden_terms: Iterable[str] = (),
) -> list[Finding]:
    normalized_root = root.resolve()
    normalized_terms = tuple(term.casefold() for term in forbidden_terms if term.strip())
    findings: list[Finding] = []

    for path in paths:
        content = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(content.splitlines(), start=1):
            for rule_id, pattern in _RULES:
                if pattern.search(line):
                    findings.append(Finding(rule_id=rule_id, path=path, line_number=line_number))
            folded_line = line.casefold()
            if any(term in folded_line for term in normalized_terms):
                findings.append(
                    Finding(
                        rule_id="FORBIDDEN_TERM",
                        path=path,
                        line_number=line_number,
                    )
                )

    return sorted(
        findings,
        key=lambda finding: (
            _display_path(finding.path, normalized_root),
            finding.line_number,
            finding.rule_id,
        ),
    )


def format_findings(findings: Iterable[Finding], *, root: Path) -> str:
    normalized_root = root.resolve()
    return "\n".join(
        f"{_display_path(finding.path, normalized_root)}:{finding.line_number}: {finding.rule_id}"
        for finding in findings
    )


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.name


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan Git-publishable files without printing matched values."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--forbidden-term",
        action="append",
        default=[],
        help="Reject a case-insensitive environment-specific term without echoing it.",
    )
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    paths = collect_publishable_paths(root)
    findings = audit_paths(paths, root=root, forbidden_terms=arguments.forbidden_term)

    if findings:
        print(format_findings(findings, root=root))
        print(f"Publication audit failed: {len(findings)} finding(s) in {len(paths)} file(s).")
        return 1

    print(f"Publication audit passed: {len(paths)} file(s) scanned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
