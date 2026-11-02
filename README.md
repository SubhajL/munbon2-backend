# Munbon Irrigation Control System Backend

A microservice-based solution for automated water control and management in Thailand's Munbon Irrigation Project.

## ⚠️ Security Notice

Current status: [Development completion register](docs/development/DEVELOPMENT_COMPLETION_REGISTER.md).

Historical source scrubbing and documented July 11 Git-history work do **not** prove that affected credentials were rotated or that all current refs/artifact carriers are clear. Source-secret findings remain S01 work; owner rotation/revocation evidence is O-SEC; reconciliation of documented history work is O-HIST. Treat previously exposed credentials as compromised until the owner provides a verified disposition.

Do not publish credential values or authenticate with old source literals. Do not automatically delete dirty checkouts, repeat history rewriting, force-push, or edit operator `.env` files. Preserve unique local work first; any rotation, re-clone/cutover or additional history remediation needs a separately approved owner procedure. Source cleanup alone is not security closure.

## Quick Start

1. Copy `.env.example` to `.env` and fill in your credentials
2. Install dependencies for each service
3. Start services as needed

## Documentation

All documentation has been moved to the `docs/` directory.

## Project Structure

```
/munbon2-backend/
├── /services/          # Microservices
├── /shared/            # Shared libraries
├── /scripts/           # Deployment and utility scripts
├── /docs/              # All documentation
└── .env.example        # Environment template
```

## Security Best Practices

- Never commit `.env` files
- Use environment variables for credentials
- Rotate credentials regularly
- Use AWS IAM roles when possible