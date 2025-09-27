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
exports.LoginAttempt = exports.LoginAttemptStatus = void 0;
const typeorm_1 = require("typeorm");
const user_entity_1 = require("./user.entity");
var LoginAttemptStatus;
(function (LoginAttemptStatus) {
    LoginAttemptStatus["SUCCESS"] = "success";
    LoginAttemptStatus["FAILED"] = "failed";
    LoginAttemptStatus["BLOCKED"] = "blocked";
})(LoginAttemptStatus || (exports.LoginAttemptStatus = LoginAttemptStatus = {}));
let LoginAttempt = class LoginAttempt {
    id;
    email;
    userId;
    user;
    status;
    ip;
    userAgent;
    reason;
    countryCode;
    city;
    metadata;
    createdAt;
};
exports.LoginAttempt = LoginAttempt;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], LoginAttempt.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)(),
    __metadata("design:type", String)
], LoginAttempt.prototype, "email", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'user_id' }),
    __metadata("design:type", String)
], LoginAttempt.prototype, "userId", void 0);
__decorate([
    (0, typeorm_1.ManyToOne)(() => user_entity_1.User, (user) => user.loginAttempts, {
        nullable: true,
        onDelete: 'CASCADE'
    }),
    (0, typeorm_1.JoinColumn)({ name: 'user_id' }),
    __metadata("design:type", user_entity_1.User)
], LoginAttempt.prototype, "user", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'enum',
        enum: LoginAttemptStatus,
    }),
    __metadata("design:type", String)
], LoginAttempt.prototype, "status", void 0);
__decorate([
    (0, typeorm_1.Column)(),
    __metadata("design:type", String)
], LoginAttempt.prototype, "ip", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'user_agent' }),
    __metadata("design:type", String)
], LoginAttempt.prototype, "userAgent", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true }),
    __metadata("design:type", String)
], LoginAttempt.prototype, "reason", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'country_code' }),
    __metadata("design:type", String)
], LoginAttempt.prototype, "countryCode", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true }),
    __metadata("design:type", String)
], LoginAttempt.prototype, "city", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'jsonb', nullable: true }),
    __metadata("design:type", Object)
], LoginAttempt.prototype, "metadata", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], LoginAttempt.prototype, "createdAt", void 0);
exports.LoginAttempt = LoginAttempt = __decorate([
    (0, typeorm_1.Entity)('login_attempts'),
    (0, typeorm_1.Index)(['email', 'createdAt']),
    (0, typeorm_1.Index)(['ip', 'createdAt'])
], LoginAttempt);
//# sourceMappingURL=login-attempt.entity.js.map