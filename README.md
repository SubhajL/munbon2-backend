# Munbon Irrigation Control System Backend

A microservice-based solution for automated water control and management in Thailand's Munbon Irrigation Project.

## ⚠️ Security Notice

This repository has been cleaned to remove exposed credentials. All team members must:
1. Delete their local copies
2. Re-clone this repository
3. Update their local .env files with new credentials

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