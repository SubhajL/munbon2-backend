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
exports.TwoFactorSecret = void 0;
const typeorm_1 = require("typeorm");
const user_entity_1 = require("./user.entity");
let TwoFactorSecret = class TwoFactorSecret {
    id;
    userId;
    user;
    secret;
    backupCodes;
    usedBackupCodes;
    verified;
    verifiedAt;
    lastUsedAt;
    createdAt;
    updatedAt;
    useBackupCode(code) {
        const index = this.backupCodes.indexOf(code);
        if (index > -1 && !this.usedBackupCodes.includes(code)) {
            this.usedBackupCodes.push(code);
            this.lastUsedAt = new Date();
            return true;
        }
        return false;
    }
    hasUnusedBackupCodes() {
        return this.backupCodes.length > this.usedBackupCodes.length;
    }
};
exports.TwoFactorSecret = TwoFactorSecret;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], TwoFactorSecret.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'user_id', unique: true }),
    __metadata("design:type", String)
], TwoFactorSecret.prototype, "userId", void 0);
__decorate([
    (0, typeorm_1.OneToOne)(() => user_entity_1.User, { onDelete: 'CASCADE' }),
    (0, typeorm_1.JoinColumn)({ name: 'user_id' }),
    __metadata("design:type", user_entity_1.User)
], TwoFactorSecret.prototype, "user", void 0);
__decorate([
    (0, typeorm_1.Column)(),
    __metadata("design:type", String)
], TwoFactorSecret.prototype, "secret", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'backup_codes', type: 'text', array: true }),
    __metadata("design:type", Array)
], TwoFactorSecret.prototype, "backupCodes", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'used_backup_codes', type: 'text', array: true, default: [] }),
    __metadata("design:type", Array)
], TwoFactorSecret.prototype, "usedBackupCodes", void 0);
__decorate([
    (0, typeorm_1.Column)({ default: false }),
    __metadata("design:type", Boolean)
], TwoFactorSecret.prototype, "verified", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'verified_at' }),
    __metadata("design:type", Date)
], TwoFactorSecret.prototype, "verifiedAt", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'last_used_at' }),
    __metadata("design:type", Date)
], TwoFactorSecret.prototype, "lastUsedAt", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], TwoFactorSecret.prototype, "createdAt", void 0);
__decorate([
    (0, typeorm_1.UpdateDateColumn)({ name: 'updated_at' }),
    __metadata("design:type", Date)
], TwoFactorSecret.prototype, "updatedAt", void 0);
exports.TwoFactorSecret = TwoFactorSecret = __decorate([
    (0, typeorm_1.Entity)('two_factor_secrets'),
    (0, typeorm_1.Index)(['userId'], { unique: true })
], TwoFactorSecret);
//# sourceMappingURL=two-factor-secret.entity.js.map