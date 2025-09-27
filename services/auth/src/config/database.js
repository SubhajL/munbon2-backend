"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AppDataSource = void 0;
exports.connectDatabase = connectDatabase;
const typeorm_1 = require("typeorm");
const index_1 = require("./index");
const user_entity_1 = require("../models/user.entity");
const refresh_token_entity_1 = require("../models/refresh-token.entity");
const login_attempt_entity_1 = require("../models/login-attempt.entity");
const password_reset_entity_1 = require("../models/password-reset.entity");
const two_factor_secret_entity_1 = require("../models/two-factor-secret.entity");
const audit_log_entity_1 = require("../models/audit-log.entity");
const session_entity_1 = require("../models/session.entity");
const role_entity_1 = require("../models/role.entity");
const permission_entity_1 = require("../models/permission.entity");
exports.AppDataSource = new typeorm_1.DataSource({
    type: 'postgres',
    url: index_1.config.database.url,
    ssl: index_1.config.database.ssl ? { rejectUnauthorized: false } : false,
    synchronize: index_1.config.env === 'development',
    logging: index_1.config.env === 'development' && index_1.config.logging.level === 'debug',
    entities: [
        user_entity_1.User,
        refresh_token_entity_1.RefreshToken,
        login_attempt_entity_1.LoginAttempt,
        password_reset_entity_1.PasswordReset,
        two_factor_secret_entity_1.TwoFactorSecret,
        audit_log_entity_1.AuditLog,
        session_entity_1.Session,
        role_entity_1.Role,
        permission_entity_1.Permission,
    ],
    migrations: ['src/migrations/*.ts'],
    subscribers: ['src/subscribers/*.ts'],
    schema: 'auth',
    poolSize: 10,
    extra: {
        max: 20,
        idleTimeoutMillis: 30000,
        connectionTimeoutMillis: 2000,
    },
});
async function connectDatabase() {
    try {
        await exports.AppDataSource.initialize();
        await exports.AppDataSource.query(`CREATE SCHEMA IF NOT EXISTS auth`);
        if (index_1.config.env === 'production') {
            await exports.AppDataSource.runMigrations();
        }
    }
    catch (error) {
        throw new Error(`Database connection failed: ${error}`);
    }
}
//# sourceMappingURL=database.js.map