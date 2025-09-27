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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.User = exports.UserType = exports.UserStatus = void 0;
const typeorm_1 = require("typeorm");
const class_validator_1 = require("class-validator");
const bcrypt_1 = __importDefault(require("bcrypt"));
const config_1 = require("../config");
const role_entity_1 = require("./role.entity");
const refresh_token_entity_1 = require("./refresh-token.entity");
const login_attempt_entity_1 = require("./login-attempt.entity");
const audit_log_entity_1 = require("./audit-log.entity");
var UserStatus;
(function (UserStatus) {
    UserStatus["ACTIVE"] = "active";
    UserStatus["INACTIVE"] = "inactive";
    UserStatus["LOCKED"] = "locked";
    UserStatus["SUSPENDED"] = "suspended";
})(UserStatus || (exports.UserStatus = UserStatus = {}));
var UserType;
(function (UserType) {
    UserType["FARMER"] = "farmer";
    UserType["GOVERNMENT_OFFICIAL"] = "government_official";
    UserType["ORGANIZATION"] = "organization";
    UserType["RESEARCHER"] = "researcher";
    UserType["SYSTEM_ADMIN"] = "system_admin";
})(UserType || (exports.UserType = UserType = {}));
let User = class User {
    id;
    email;
    password;
    firstName;
    lastName;
    citizenId;
    phoneNumber;
    userType;
    status;
    emailVerified;
    emailVerifiedAt;
    twoFactorEnabled;
    thaiDigitalId;
    profileImage;
    metadata;
    lastLoginAt;
    lastLoginIp;
    failedLoginAttempts;
    lockedUntil;
    organizationId;
    zoneId;
    roles;
    refreshTokens;
    loginAttempts;
    auditLogs;
    createdAt;
    updatedAt;
    async hashPassword() {
        if (this.password && !this.password.startsWith('$2b$')) {
            this.password = await bcrypt_1.default.hash(this.password, config_1.config.security.bcryptRounds);
        }
    }
    async comparePassword(password) {
        return bcrypt_1.default.compare(password, this.password);
    }
    hasRole(roleName) {
        return this.roles.some((role) => role.name === roleName);
    }
    hasPermission(permissionName) {
        return this.roles.some((role) => role.permissions.some((permission) => permission.name === permissionName));
    }
    isLocked() {
        return this.status === UserStatus.LOCKED ||
            (this.lockedUntil && this.lockedUntil > new Date());
    }
    toJSON() {
        const { password, ...user } = this;
        return user;
    }
};
exports.User = User;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], User.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ unique: true }),
    (0, class_validator_1.IsEmail)(),
    __metadata("design:type", String)
], User.prototype, "email", void 0);
__decorate([
    (0, typeorm_1.Column)({ select: false }),
    (0, class_validator_1.MinLength)(8),
    __metadata("design:type", String)
], User.prototype, "password", void 0);
__decorate([
    (0, typeorm_1.Column)(),
    (0, class_validator_1.IsNotEmpty)(),
    __metadata("design:type", String)
], User.prototype, "firstName", void 0);
__decorate([
    (0, typeorm_1.Column)(),
    (0, class_validator_1.IsNotEmpty)(),
    __metadata("design:type", String)
], User.prototype, "lastName", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'citizen_id' }),
    __metadata("design:type", String)
], User.prototype, "citizenId", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'phone_number' }),
    __metadata("design:type", String)
], User.prototype, "phoneNumber", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'enum',
        enum: UserType,
        default: UserType.FARMER,
    }),
    __metadata("design:type", String)
], User.prototype, "userType", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'enum',
        enum: UserStatus,
        default: UserStatus.ACTIVE,
    }),
    __metadata("design:type", String)
], User.prototype, "status", void 0);
__decorate([
    (0, typeorm_1.Column)({ default: false, name: 'email_verified' }),
    __metadata("design:type", Boolean)
], User.prototype, "emailVerified", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'email_verified_at' }),
    __metadata("design:type", Date)
], User.prototype, "emailVerifiedAt", void 0);
__decorate([
    (0, typeorm_1.Column)({ default: false, name: 'two_factor_enabled' }),
    __metadata("design:type", Boolean)
], User.prototype, "twoFactorEnabled", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'thai_digital_id' }),
    __metadata("design:type", String)
], User.prototype, "thaiDigitalId", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'profile_image' }),
    __metadata("design:type", String)
], User.prototype, "profileImage", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'jsonb', nullable: true }),
    __metadata("design:type", Object)
], User.prototype, "metadata", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'last_login_at' }),
    __metadata("design:type", Date)
], User.prototype, "lastLoginAt", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'last_login_ip' }),
    __metadata("design:type", String)
], User.prototype, "lastLoginIp", void 0);
__decorate([
    (0, typeorm_1.Column)({ default: 0, name: 'failed_login_attempts' }),
    __metadata("design:type", Number)
], User.prototype, "failedLoginAttempts", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'locked_until' }),
    __metadata("design:type", Date)
], User.prototype, "lockedUntil", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'organization_id' }),
    __metadata("design:type", String)
], User.prototype, "organizationId", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true, name: 'zone_id' }),
    __metadata("design:type", String)
], User.prototype, "zoneId", void 0);
__decorate([
    (0, typeorm_1.ManyToMany)(() => role_entity_1.Role, (role) => role.users, { eager: true }),
    (0, typeorm_1.JoinTable)({
        name: 'user_roles',
        joinColumn: { name: 'user_id', referencedColumnName: 'id' },
        inverseJoinColumn: { name: 'role_id', referencedColumnName: 'id' },
    }),
    __metadata("design:type", Array)
], User.prototype, "roles", void 0);
__decorate([
    (0, typeorm_1.OneToMany)(() => refresh_token_entity_1.RefreshToken, (token) => token.user),
    __metadata("design:type", Array)
], User.prototype, "refreshTokens", void 0);
__decorate([
    (0, typeorm_1.OneToMany)(() => login_attempt_entity_1.LoginAttempt, (attempt) => attempt.user),
    __metadata("design:type", Array)
], User.prototype, "loginAttempts", void 0);
__decorate([
    (0, typeorm_1.OneToMany)(() => audit_log_entity_1.AuditLog, (log) => log.user),
    __metadata("design:type", Array)
], User.prototype, "auditLogs", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], User.prototype, "createdAt", void 0);
__decorate([
    (0, typeorm_1.UpdateDateColumn)({ name: 'updated_at' }),
    __metadata("design:type", Date)
], User.prototype, "updatedAt", void 0);
__decorate([
    (0, typeorm_1.BeforeInsert)(),
    (0, typeorm_1.BeforeUpdate)(),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], User.prototype, "hashPassword", null);
exports.User = User = __decorate([
    (0, typeorm_1.Entity)('users'),
    (0, typeorm_1.Index)(['email'], { unique: true }),
    (0, typeorm_1.Index)(['citizenId'], { unique: true, where: 'citizen_id IS NOT NULL' }),
    (0, typeorm_1.Index)(['phoneNumber'], { unique: true, where: 'phone_number IS NOT NULL' })
], User);
//# sourceMappingURL=user.entity.js.map