# Security Policy

## Supported versions

Security fixes are published via tagged releases on [septigram/oil-oss](https://github.com/septigram/oil-oss). Use the latest release when deploying.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Report issues privately via GitHub Security Advisories:

https://github.com/septigram/oil-oss/security/advisories/new

If Advisories are unavailable, open a minimal GitHub issue asking for a private contact channel without disclosing exploit details.

We aim to acknowledge reports within a reasonable timeframe.

## Deployment notes

- Change default passwords (`OIL_BOOTSTRAP_PASSWORD`, `OIL_SESSION_SECRET`) in production
- Do not commit `.env` or real `config/config.yaml` with secrets
- Restrict network access to Tsurugi (port 12345) in production deployments
