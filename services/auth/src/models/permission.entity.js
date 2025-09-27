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
exports.PERMISSIONS = exports.Permission = void 0;
const typeorm_1 = require("typeorm");
const role_entity_1 = require("./role.entity");
let Permission = class Permission {
    id;
    name;
    displayName;
    description;
    resource;
    action;
    isActive;
    conditions;
    roles;
    createdAt;
    updatedAt;
};
exports.Permission = Permission;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], Permission.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ unique: true }),
    __metadata("design:type", String)
], Permission.prototype, "name", void 0);
__decorate([
    (0, typeorm_1.Column)(),
    __metadata("design:type", String)
], Permission.prototype, "displayName", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true }),
    __metadata("design:type", String)
], Permission.prototype, "description", void 0);
__decorate([
    (0, typeorm_1.Column)(),
    __metadata("design:type", String)
], Permission.prototype, "resource", void 0);
__decorate([
    (0, typeorm_1.Column)(),
    __metadata("design:type", String)
], Permission.prototype, "action", void 0);
__decorate([
    (0, typeorm_1.Column)({ default: true }),
    __metadata("design:type", Boolean)
], Permission.prototype, "isActive", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'jsonb', nullable: true }),
    __metadata("design:type", Object)
], Permission.prototype, "conditions", void 0);
__decorate([
    (0, typeorm_1.ManyToMany)(() => role_entity_1.Role, (role) => role.permissions),
    __metadata("design:type", Array)
], Permission.prototype, "roles", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], Permission.prototype, "createdAt", void 0);
__decorate([
    (0, typeorm_1.UpdateDateColumn)({ name: 'updated_at' }),
    __metadata("design:type", Date)
], Permission.prototype, "updatedAt", void 0);
exports.Permission = Permission = __decorate([
    (0, typeorm_1.Entity)('permissions'),
    (0, typeorm_1.Index)(['name'], { unique: true }),
    (0, typeorm_1.Index)(['resource', 'action'])
], Permission);
exports.PERMISSIONS = {
    SYSTEM_ADMIN: 'system.admin',
    SYSTEM_CONFIG: 'system.config',
    USERS_READ: 'users.read',
    USERS_WRITE: 'users.write',
    USERS_DELETE: 'users.delete',
    USERS_MANAGE_ROLES: 'users.manage_roles',
    SENSORS_READ: 'sensors.read',
    SENSORS_WRITE: 'sensors.write',
    SENSORS_DELETE: 'sensors.delete',
    SENSORS_CALIBRATE: 'sensors.calibrate',
    GATES_READ: 'gates.read',
    GATES_CONTROL: 'gates.control',
    PUMPS_READ: 'pumps.read',
    PUMPS_CONTROL: 'pumps.control',
    VALVES_READ: 'valves.read',
    VALVES_CONTROL: 'valves.control',
    GIS_READ: 'gis.read',
    GIS_WRITE: 'gis.write',
    GIS_ADMIN: 'gis.admin',
    REPORTS_READ: 'reports.read',
    REPORTS_GENERATE: 'reports.generate',
    REPORTS_EXPORT: 'reports.export',
    AI_READ: 'ai.read',
    AI_EXECUTE: 'ai.execute',
    AI_TRAIN: 'ai.train',
    IRRIGATION_VIEW_SCHEDULE: 'irrigation.view_schedule',
    IRRIGATION_CREATE_SCHEDULE: 'irrigation.create_schedule',
    IRRIGATION_MODIFY_SCHEDULE: 'irrigation.modify_schedule',
    IRRIGATION_DELETE_SCHEDULE: 'irrigation.delete_schedule',
    ALERTS_READ: 'alerts.read',
    ALERTS_ACKNOWLEDGE: 'alerts.acknowledge',
    ALERTS_CONFIGURE: 'alerts.configure',
};
//# sourceMappingURL=permission.entity.js.map