"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.RefreshToken = void 0;
const typeorm_1 = require("typeorm");
const user_entity_1 = require("./user.entity");
let RefreshToken = class RefreshToken {
    id;
    token;
    userId;
    user;
    deviceId;
    deviceName;
    userAgent;
    ip;
    isActive;
    expiresAt;
    revokedAt;
    revokedBy;
    revokeReason;
    createdAt;
    isExpired() {
        return this.expiresAt < new Date();
    }
    isValid() {
        return this.isActive && !this.isExpired() && !this.revokedAt;
    }
    revoke(userId, reason) {
        this.isActive = false;
        this.revokedAt = new Date();
        this.revokedBy = userId;
        this.revokeReason = reason;
    }
};
exports.RefreshToken = RefreshToken;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], RefreshToken.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ unique: true }),
    __metadata("design:type", String)
], RefreshToken.prototype, "token", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'user_id' }),
    __metadata("design:type", String)
], RefreshToken.prototype, "userId", void 0);
__decorate([
    (0, typeorm_1.ManyToOne)(() => user_entity_1.User, (user) => user.refreshTokens, { onDelete: 'CASCADE' }),
    (0, typeorm_1.JoinColumn)({ name: 'user_id' }),
    __metadata("design:type", user_entity_1.User)
], RefreshToken.prototype, "user", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'device_id' }),
    __metadata("design:type", String)
], RefreshToken.prototype, "deviceId", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'device_name' }),
    __metadata("design:type", String)
], RefreshToken.prototype, "deviceName", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'user_agent' }),
    __metadata("design:type", String)
], RefreshToken.prototype, "userAgent", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true }),
    __metadata("design:type", String)
], RefreshToken.prototype, "ip", void 0);
__decorate([
    (0, typeorm_1.Column)({ default: true, name: 'is_active' }),
    __metadata("design:type", Boolean)
], RefreshToken.prototype, "isActive", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'expires_at' }),
    __metadata("design:type", Date)
], RefreshToken.prototype, "expiresAt", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'revoked_at' }),
    __metadata("design:type", Date)
], RefreshToken.prototype, "revokedAt", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'revoked_by' }),
    __metadata("design:type", String)
], RefreshToken.prototype, "revokedBy", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'revoke_reason' }),
    __metadata("design:type", String)
], RefreshToken.prototype, "revokeReason", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], RefreshToken.prototype, "createdAt", void 0);
exports.RefreshToken = RefreshToken = __decorate([
    (0, typeorm_1.Entity)('refresh_tokens'),
    (0, typeorm_1.Index)(['token'], { unique: true }),
    (0, typeorm_1.Index)(['userId', 'isActive']),
    (0, typeorm_1.Index)(['expiresAt'])
], RefreshToken);
//# sourceMappingURL=refresh-token.entity.js.map