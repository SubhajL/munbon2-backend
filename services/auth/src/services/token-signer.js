"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.signAuthTokenPair = signAuthTokenPair;
const jsonwebtoken_1 = require("jsonwebtoken");
const crypto_1 = require("crypto");
// Signs the access + refresh token pair for `principal`, embedding a UNIQUE jti
// per token (via jsonwebtoken's `jwtid`). The jti is what lets the scheduler's
// fail-closed revocation identify/revoke an individual token and is REQUIRED by
// its strict claim policy (services/scheduler core/auth.validate_access_token_claims:
// iss/aud/type/jti/roles). iss/aud come from `jwtConfig`; `type` distinguishes
// the two tokens; `roles` carries RBAC. `makeJti` is injectable so tests are
// deterministic; it defaults to a random UUID v4 and MUST yield a fresh,
// non-blank id on each call (reusing one would give both tokens the same
// revocation identity).
function signAuthTokenPair(principal, jwtConfig, makeJti = crypto_1.randomUUID) {
    const base = {
        sub: principal.sub,
        email: principal.email,
        roles: principal.roles,
    };
    const accessToken = jsonwebtoken_1.sign({ ...base, type: 'access' }, jwtConfig.secret, {
        expiresIn: jwtConfig.accessTokenExpiresIn,
        issuer: jwtConfig.issuer,
        audience: jwtConfig.audience,
        jwtid: makeJti(),
    });
    const refreshToken = jsonwebtoken_1.sign({ ...base, type: 'refresh' }, jwtConfig.secret, {
        expiresIn: jwtConfig.refreshTokenExpiresIn,
        issuer: jwtConfig.issuer,
        audience: jwtConfig.audience,
        jwtid: makeJti(),
    });
    // 15 minutes, matching the access-token lifetime advertised to clients.
    const expiresIn = 15 * 60;
    return { accessToken, refreshToken, expiresIn };
}
//# sourceMappingURL=token-signer.js.map
