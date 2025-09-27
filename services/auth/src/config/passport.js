"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.setupPassport = setupPassport;
const passport_1 = __importDefault(require("passport"));
const passport_local_1 = require("passport-local");
const passport_jwt_1 = require("passport-jwt");
const passport_oauth2_1 = require("passport-oauth2");
const index_1 = require("./index");
const user_service_1 = require("../services/user.service");
const auth_service_1 = require("../services/auth.service");
const logger_1 = require("../utils/logger");
function setupPassport() {
    passport_1.default.use(new passport_local_1.Strategy({
        usernameField: 'email',
        passwordField: 'password',
    }, async (email, password, done) => {
        try {
            const user = await auth_service_1.authService.validateUser(email, password);
            if (!user) {
                return done(null, false, { message: 'Invalid credentials' });
            }
            return done(null, user);
        }
        catch (error) {
            logger_1.logger.error('Local strategy error:', error);
            return done(error);
        }
    }));
    passport_1.default.use(new passport_jwt_1.Strategy({
        jwtFromRequest: passport_jwt_1.ExtractJwt.fromAuthHeaderAsBearerToken(),
        secretOrKey: index_1.config.jwt.secret,
        issuer: index_1.config.jwt.issuer,
        audience: index_1.config.jwt.audience,
    }, async (payload, done) => {
        try {
            const user = await user_service_1.userService.findById(payload.sub);
            if (!user || !user.isActive) {
                return done(null, false);
            }
            return done(null, user);
        }
        catch (error) {
            logger_1.logger.error('JWT strategy error:', error);
            return done(error, false);
        }
    }));
    passport_1.default.use('thai-digital-id', new passport_oauth2_1.Strategy({
        authorizationURL: index_1.config.thaiDigitalId.authUrl,
        tokenURL: index_1.config.thaiDigitalId.tokenUrl,
        clientID: index_1.config.thaiDigitalId.clientId,
        clientSecret: index_1.config.thaiDigitalId.clientSecret,
        callbackURL: `${index_1.config.oauth.callbackUrl}/thai-digital-id`,
        scope: ['openid', 'profile', 'email', 'citizen_id'],
    }, async (accessToken, refreshToken, profile, done) => {
        try {
            const userInfo = await auth_service_1.authService.getThaiDigitalIdUserInfo(accessToken);
            const user = await auth_service_1.authService.findOrCreateFromThaiDigitalId(userInfo);
            return done(null, user);
        }
        catch (error) {
            logger_1.logger.error('Thai Digital ID strategy error:', error);
            return done(error);
        }
    }));
    passport_1.default.serializeUser((user, done) => {
        done(null, user.id);
    });
    passport_1.default.deserializeUser(async (id, done) => {
        try {
            const user = await user_service_1.userService.findById(id);
            done(null, user);
        }
        catch (error) {
            done(error);
        }
    });
}
//# sourceMappingURL=passport.js.map