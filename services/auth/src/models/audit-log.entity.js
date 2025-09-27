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
exports.AuditLog = exports.AuditAction = void 0;
const typeorm_1 = require("typeorm");
const user_entity_1 = require("./user.entity");
var AuditAction;
(function (AuditAction) {
    AuditAction["LOGIN"] = "login";
    AuditAction["LOGOUT"] = "logout";
    AuditAction["LOGIN_FAILED"] = "login_failed";
    AuditAction["TOKEN_REFRESH"] = "token_refresh";
    AuditAction["PASSWORD_RESET_REQUEST"] = "password_reset_request";
    AuditAction["PASSWORD_RESET_COMPLETE"] = "password_reset_complete";
    AuditAction["USER_CREATE"] = "user_create";
    AuditAction["USER_UPDATE"] = "user_update";
    AuditAction["USER_DELETE"] = "user_delete";
    AuditAction["USER_LOCK"] = "user_lock";
    AuditAction["USER_UNLOCK"] = "user_unlock";
    AuditAction["ROLE_ASSIGN"] = "role_assign";
    AuditAction["ROLE_REVOKE"] = "role_revoke";
    AuditAction["PERMISSION_GRANT"] = "permission_grant";
    AuditAction["PERMISSION_REVOKE"] = "permission_revoke";
    AuditAction["TWO_FACTOR_ENABLE"] = "two_factor_enable";
    AuditAction["TWO_FACTOR_DISABLE"] = "two_factor_disable";
    AuditAction["TWO_FACTOR_VERIFY"] = "two_factor_verify";
    AuditAction["SUSPICIOUS_ACTIVITY"] = "suspicious_activity";
    AuditAction["ACCESS_DENIED"] = "access_denied";
})(AuditAction || (exports.AuditAction = AuditAction = {}));
let AuditLog = class AuditLog {
    id;
    userId;
    user;
    action;
    resource;
    description;
    ip;
    userAgent;
    oldValues;
    newValues;
    metadata;
    success;
    errorMessage;
    createdAt;
};
exports.AuditLog = AuditLog;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], AuditLog.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'user_id' }),
    __metadata("design:type", String)
], AuditLog.prototype, "userId", void 0);
__decorate([
    (0, typeorm_1.ManyToOne)(() => user_entity_1.User, (user) => user.auditLogs, {
        nullable: true,
        onDelete: 'SET NULL'
    }),
    (0, typeorm_1.JoinColumn)({ name: 'user_id' }),
    __metadata("design:type", user_entity_1.User)
], AuditLog.prototype, "user", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'enum',
        enum: AuditAction,
    }),
    __metadata("design:type", String)
], AuditLog.prototype, "action", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true }),
    __metadata("design:type", String)
], AuditLog.prototype, "resource", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true }),
    __metadata("design:type", String)
], AuditLog.prototype, "description", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true }),
    __metadata("design:type", String)
], AuditLog.prototype, "ip", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'user_agent' }),
    __metadata("design:type", String)
], AuditLog.prototype, "userAgent", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'jsonb', nullable: true, name: 'old_values' }),
    __metadata("design:type", Object)
], AuditLog.prototype, "oldValues", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'jsonb', nullable: true, name: 'new_values' }),
    __metadata("design:type", Object)
], AuditLog.prototype, "newValues", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'jsonb', nullable: true }),
    __metadata("design:type", Object)
], AuditLog.prototype, "metadata", void 0);
__decorate([
    (0, typeorm_1.Column)({ default: true }),
    __metadata("design:type", Boolean)
], AuditLog.prototype, "success", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'error_message' }),
    __metadata("design:type", String)
], AuditLog.prototype, "errorMessage", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], AuditLog.prototype, "createdAt", void 0);
exports.AuditLog = AuditLog = __decorate([
    (0, typeorm_1.Entity)('audit_logs'),
    (0, typeorm_1.Index)(['userId', 'createdAt']),
    (0, typeorm_1.Index)(['action', 'createdAt']),
    (0, typeorm_1.Index)(['ip'])
], AuditLog);
//# sourceMappingURL=audit-log.entity.js.map