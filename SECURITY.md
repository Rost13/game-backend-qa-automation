# Security Policy

## Reporting a vulnerability

Do not open a public issue for suspected credential exposure or a security
vulnerability. Use GitHub's private vulnerability reporting or a private
Security Advisory for this repository.

Include only the minimum evidence needed to reproduce the problem. Remove or
redact authorization headers, cookies, tokens, passwords, connection strings,
personal data, and live environment addresses.

## Credential exposure

Treat an exposed credential as compromised even when it was quickly removed.
Revoke or rotate it first, then remove it from the current tree and Git history,
and run the publication audit before publishing another revision.
