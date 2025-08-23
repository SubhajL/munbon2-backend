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
exports.WaterSource = exports.WaterSourceType = void 0;
const typeorm_1 = require("typeorm");
var WaterSourceType;
(function (WaterSourceType) {
    WaterSourceType["RESERVOIR"] = "reservoir";
    WaterSourceType["RIVER"] = "river";
    WaterSourceType["POND"] = "pond";
    WaterSourceType["WELL"] = "well";
    WaterSourceType["SPRING"] = "spring";
    WaterSourceType["DAM"] = "dam";
})(WaterSourceType || (exports.WaterSourceType = WaterSourceType = {}));
let WaterSource = class WaterSource {
    id;
    code;
    name;
    nameTh;
    type;
    geometry;
    area;
    maxCapacity;
    currentVolume;
    waterLevel;
    qualityIndex;
    properties;
    createdAt;
    updatedAt;
};
exports.WaterSource = WaterSource;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], WaterSource.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ unique: true }),
    __metadata("design:type", String)
], WaterSource.prototype, "code", void 0);
__decorate([
    (0, typeorm_1.Column)(),
    __metadata("design:type", String)
], WaterSource.prototype, "name", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'name_th', nullable: true }),
    __metadata("design:type", String)
], WaterSource.prototype, "nameTh", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'enum',
        enum: WaterSourceType,
    }),
    __metadata("design:type", String)
], WaterSource.prototype, "type", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'geometry',
        spatialFeatureType: 'Geometry',
        srid: 4326,
    }),
    __metadata("design:type", Object)
], WaterSource.prototype, "geometry", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'float', nullable: true }),
    __metadata("design:type", Number)
], WaterSource.prototype, "area", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'max_capacity', type: 'float', nullable: true }),
    __metadata("design:type", Number)
], WaterSource.prototype, "maxCapacity", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'current_volume', type: 'float', nullable: true }),
    __metadata("design:type", Number)
], WaterSource.prototype, "currentVolume", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'water_level', type: 'float', nullable: true }),
    __metadata("design:type", Number)
], WaterSource.prototype, "waterLevel", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'quality_index', type: 'float', nullable: true }),
    __metadata("design:type", Number)
], WaterSource.prototype, "qualityIndex", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'jsonb', nullable: true }),
    __metadata("design:type", Object)
], WaterSource.prototype, "properties", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], WaterSource.prototype, "createdAt", void 0);
__decorate([
    (0, typeorm_1.UpdateDateColumn)({ name: 'updated_at' }),
    __metadata("design:type", Date)
], WaterSource.prototype, "updatedAt", void 0);
exports.WaterSource = WaterSource = __decorate([
    (0, typeorm_1.Entity)('water_sources'),
    (0, typeorm_1.Index)(['code'], { unique: true }),
    (0, typeorm_1.Index)(['type'])
], WaterSource);
//# sourceMappingURL=water-source.entity.js.map