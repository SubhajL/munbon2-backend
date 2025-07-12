# Authentication & Authorization Service

This service handles all authentication and authorization for the Munbon Backend system.

## Features

- **OAuth 2.0 Authentication** with JWT tokens
- **Thai Digital ID Integration** for government authentication
- **Two-Factor Authentication (2FA)** with TOTP
- **Role-Based Access Control (RBAC)** with granular permissions
- **Session Management** with Redis
- **Password Reset** via email
- **Account Lockout** after failed attempts
- **Audit Logging** for security events
- **Rate Limiting** to prevent brute force attacks

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Kong Gateway  │────▶│   Auth Service  │────▶│   PostgreSQL    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │                          │
                               ▼                          ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │      Redis      │     │  Auth Schema    │
                        │  (Sessions)     │     │  (Users, Roles) │
                        └─────────────────┘     └─────────────────┘
```

## API Endpoints

### Public Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login with email/password |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/logout` | Logout user |
| POST | `/api/v1/auth/forgot-password` | Request password reset |
| POST | `/api/v1/auth/reset-password` | Reset password with token |
| GET | `/api/v1/auth/verify-email/:token` | Verify email address |

### Protected Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/auth/me` | Get current user |
| POST | `/api/v1/auth/change-password` | Change password |
| POST | `/api/v1/auth/enable-2fa` | Enable 2FA |
| POST | `/api/v1/auth/disable-2fa` | Disable 2FA |
| POST | `/api/v1/auth/verify-2fa` | Verify 2FA code |
| GET | `/api/v1/auth/sessions` | Get active sessions |
| DELETE | `/api/v1/auth/sessions/:id` | Revoke session |

### OAuth Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/oauth/thai-digital-id` | Thai Digital ID OAuth |
| GET | `/api/v1/oauth/thai-digital-id/callback` | OAuth callback |

## User Types

- **FARMER** - Basic farmer account
- **GOVERNMENT_OFFICIAL** - Thai government officials
- **ORGANIZATION** - Organization representatives
- **RESEARCHER** - Research institutions
- **SYSTEM_ADMIN** - System administrators

## System Roles

- **super_admin** - Full system access
- **rid_admin** - RID administrator
- **zone_manager** - Zone management
- **government_official** - Government access
- **organization_admin** - Organization admin
- **farmer_premium** - Premium farmer features
- **farmer_basic** - Basic farmer access
- **researcher** - Research access
- **guest** - Limited guest access

## Environment Variables

```bash
# Server
PORT=3001
NODE_ENV=development

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/munbon_dev

# Redis
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET=your-secret-key
JWT_ACCESS_TOKEN_EXPIRES_IN=15m
JWT_REFRESH_TOKEN_EXPIRES_IN=7d

# Thai Digital ID OAuth
THAI_DIGITAL_ID_CLIENT_ID=your-client-id
THAI_DIGITAL_ID_CLIENT_SECRET=your-client-secret

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@munbon.go.th
SMTP_PASS=your-password

# Security
BCRYPT_ROUNDS=12
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION=15
```

## Development

### Install Dependencies
```bash
npm install
```

### Run Development Server
```bash
npm run dev
```

### Build for Production
```bash
npm run build
```

### Run Tests
```bash
npm test
```

## Docker

### Build Image
```bash
docker build -t munbon-auth-service .
```

### Run Container
```bash
docker run -p 3001:3001 --env-file .env munbon-auth-service
```

## Security Features

1. **Password Requirements**
   - Minimum 8 characters
   - Uppercase and lowercase letters
   - Numbers and special characters

2. **Account Protection**
   - Account lockout after 5 failed attempts
   - 15-minute lockout duration
   - Email alerts for suspicious activity

3. **Token Security**
   - Short-lived access tokens (15 minutes)
   - Refresh token rotation
   - Secure httpOnly cookies

4. **Rate Limiting**
   - 100 requests per 15 minutes per IP
   - Stricter limits on sensitive endpoints

5. **Audit Trail**
   - All authentication events logged
   - Failed login tracking
   - Permission changes tracked

## Integration with Kong

The auth service integrates with Kong API Gateway for:

1. **JWT Validation** - Kong validates JWTs on protected routes
2. **Rate Limiting** - Tiered limits based on user roles
3. **Thai Digital ID Plugin** - Custom Kong plugin for government auth
4. **Request Routing** - Kong routes `/api/v1/auth/*` to this service

## Database Schema

The service uses PostgreSQL with the following main tables:

- **users** - User accounts and profiles
- **roles** - System and custom roles
- **permissions** - Granular permissions
- **user_roles** - User-role mappings
- **role_permissions** - Role-permission mappings
- **refresh_tokens** - Active refresh tokens
- **login_attempts** - Login attempt tracking
- **password_resets** - Password reset tokens
- **two_factor_secrets** - 2FA configurations
- **audit_logs** - Security audit trail
- **sessions** - Active user sessions

## Monitoring

### Health Check Endpoints

- `/health` - Comprehensive health check
- `/health/live` - Liveness probe
- `/health/ready` - Readiness probe

### Metrics

The service exposes metrics for:
- Login success/failure rates
- Token generation rates
- 2FA usage statistics
- Account lockout events
- Password reset requests