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
exports.IrrigationBlock = void 0;
const typeorm_1 = require("typeorm");
const zone_entity_1 = require("./zone.entity");
let IrrigationBlock = class IrrigationBlock {
    id;
    code;
    name;
    geometry;
    area;
    zoneId;
    zone;
    waterAllocation;
    irrigationSchedule;
    properties;
    createdAt;
    updatedAt;
};
exports.IrrigationBlock = IrrigationBlock;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], IrrigationBlock.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ unique: true }),
    __metadata("design:type", String)
], IrrigationBlock.prototype, "code", void 0);
__decorate([
    (0, typeorm_1.Column)(),
    __metadata("design:type", String)
], IrrigationBlock.prototype, "name", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'geometry',
        spatialFeatureType: 'Polygon',
        srid: 4326,
    }),
    __metadata("design:type", Object)
], IrrigationBlock.prototype, "geometry", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'float' }),
    __metadata("design:type", Number)
], IrrigationBlock.prototype, "area", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'zone_id' }),
    __metadata("design:type", String)
], IrrigationBlock.prototype, "zoneId", void 0);
__decorate([
    (0, typeorm_1.ManyToOne)(() => zone_entity_1.Zone, (zone) => zone.irrigationBlocks),
    (0, typeorm_1.JoinColumn)({ name: 'zone_id' }),
    __metadata("design:type", zone_entity_1.Zone)
], IrrigationBlock.prototype, "zone", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'water_allocation', type: 'float', nullable: true }),
    __metadata("design:type", Number)
], IrrigationBlock.prototype, "waterAllocation", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'irrigation_schedule', type: 'jsonb', nullable: true }),
    __metadata("design:type", Array)
], IrrigationBlock.prototype, "irrigationSchedule", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'jsonb', nullable: true }),
    __metadata("design:type", Object)
], IrrigationBlock.prototype, "properties", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], IrrigationBlock.prototype, "createdAt", void 0);
__decorate([
    (0, typeorm_1.UpdateDateColumn)({ name: 'updated_at' }),
    __metadata("design:type", Date)
], IrrigationBlock.prototype, "updatedAt", void 0);
exports.IrrigationBlock = IrrigationBlock = __decorate([
    (0, typeorm_1.Entity)('irrigation_blocks'),
    (0, typeorm_1.Index)(['code'], { unique: true }),
    (0, typeorm_1.Index)(['zoneId'])
], IrrigationBlock);
//# sourceMappingURL=irrigation-block.entity.js.map