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
exports.PasswordReset = void 0;
const typeorm_1 = require("typeorm");
const user_entity_1 = require("./user.entity");
let PasswordReset = class PasswordReset {
    id;
    email;
    userId;
    user;
    token;
    expiresAt;
    used;
    usedAt;
    ip;
    userAgent;
    createdAt;
    isExpired() {
        return this.expiresAt < new Date();
    }
    isValid() {
        return !this.used && !this.isExpired();
    }
    markAsUsed() {
        this.used = true;
        this.usedAt = new Date();
    }
};
exports.PasswordReset = PasswordReset;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], PasswordReset.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)(),
    __metadata("design:type", String)
], PasswordReset.prototype, "email", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'user_id' }),
    __metadata("design:type", String)
], PasswordReset.prototype, "userId", void 0);
__decorate([
    (0, typeorm_1.ManyToOne)(() => user_entity_1.User, { onDelete: 'CASCADE' }),
    (0, typeorm_1.JoinColumn)({ name: 'user_id' }),
    __metadata("design:type", user_entity_1.User)
], PasswordReset.prototype, "user", void 0);
__decorate([
    (0, typeorm_1.Column)({ unique: true }),
    __metadata("design:type", String)
], PasswordReset.prototype, "token", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'expires_at' }),
    __metadata("design:type", Date)
], PasswordReset.prototype, "expiresAt", void 0);
__decorate([
    (0, typeorm_1.Column)({ default: false }),
    __metadata("design:type", Boolean)
], PasswordReset.prototype, "used", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'used_at' }),
    __metadata("design:type", Date)
], PasswordReset.prototype, "usedAt", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true }),
    __metadata("design:type", String)
], PasswordReset.prototype, "ip", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'user_agent' }),
    __metadata("design:type", String)
], PasswordReset.prototype, "userAgent", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], PasswordReset.prototype, "createdAt", void 0);
exports.PasswordReset = PasswordReset = __decorate([
    (0, typeorm_1.Entity)('password_resets'),
    (0, typeorm_1.Index)(['token'], { unique: true }),
    (0, typeorm_1.Index)(['email', 'expiresAt'])
], PasswordReset);
//# sourceMappingURL=password-reset.entity.js.map