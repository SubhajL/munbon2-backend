"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.generateRandomString = generateRandomString;
exports.generateSecureToken = generateSecureToken;
exports.hashString = hashString;
exports.generateBackupCodes = generateBackupCodes;
exports.constantTimeCompare = constantTimeCompare;
const crypto_1 = __importDefault(require("crypto"));
function generateRandomString(length) {
    return crypto_1.default.randomBytes(Math.ceil(length / 2)).toString('hex').slice(0, length);
}
function generateSecureToken() {
    return crypto_1.default.randomBytes(32).toString('base64url');
}
function hashString(str) {
    return crypto_1.default.createHash('sha256').update(str).digest('hex');
}
function generateBackupCodes(count = 10) {
    const codes = [];
    for (let i = 0; i < count; i++) {
        codes.push(generateRandomString(8).toUpperCase());
    }
    return codes;
}
function constantTimeCompare(a, b) {
    if (a.length !== b.length) {
        return false;
    }
    return crypto_1.default.timingSafeEqual(Buffer.from(a), Buffer.from(b));
}
//# sourceMappingURL=crypto.js.map