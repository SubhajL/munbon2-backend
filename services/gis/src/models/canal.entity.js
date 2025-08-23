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
exports.Canal = exports.CanalCondition = exports.CanalStatus = exports.CanalType = void 0;
const typeorm_1 = require("typeorm");
const zone_entity_1 = require("./zone.entity");
const gate_entity_1 = require("./gate.entity");
var CanalType;
(function (CanalType) {
    CanalType["MAIN"] = "main";
    CanalType["LATERAL"] = "lateral";
    CanalType["SUB_LATERAL"] = "sub_lateral";
    CanalType["FIELD"] = "field";
    CanalType["DRAINAGE"] = "drainage";
})(CanalType || (exports.CanalType = CanalType = {}));
var CanalStatus;
(function (CanalStatus) {
    CanalStatus["OPERATIONAL"] = "operational";
    CanalStatus["MAINTENANCE"] = "maintenance";
    CanalStatus["DAMAGED"] = "damaged";
    CanalStatus["ABANDONED"] = "abandoned";
})(CanalStatus || (exports.CanalStatus = CanalStatus = {}));
var CanalCondition;
(function (CanalCondition) {
    CanalCondition["EXCELLENT"] = "excellent";
    CanalCondition["GOOD"] = "good";
    CanalCondition["FAIR"] = "fair";
    CanalCondition["POOR"] = "poor";
    CanalCondition["CRITICAL"] = "critical";
})(CanalCondition || (exports.CanalCondition = CanalCondition = {}));
let Canal = class Canal {
    id;
    canalCode;
    canalName;
    canalType;
    lengthMeters;
    widthMeters;
    depthMeters;
    capacityCms;
    geometry;
    upstreamNodeId;
    downstreamNodeId;
    zone;
    gates;
    createdAt;
    updatedAt;
    get geoJSON() {
        return {
            type: 'Feature',
            geometry: this.geometry,
            properties: {
                id: this.id,
                canalCode: this.canalCode,
                canalName: this.canalName,
                canalType: this.canalType,
                lengthMeters: this.lengthMeters,
                widthMeters: this.widthMeters,
                depthMeters: this.depthMeters,
                capacityCms: this.capacityCms,
            },
        };
    }
};
exports.Canal = Canal;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], Canal.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'canal_code', unique: true }),
    __metadata("design:type", String)
], Canal.prototype, "canalCode", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'canal_name' }),
    __metadata("design:type", String)
], Canal.prototype, "canalName", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'canal_type', nullable: true }),
    __metadata("design:type", String)
], Canal.prototype, "canalType", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'length_meters', type: 'float' }),
    __metadata("design:type", Number)
], Canal.prototype, "lengthMeters", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'width_meters', type: 'float', nullable: true }),
    __metadata("design:type", Number)
], Canal.prototype, "widthMeters", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'depth_meters', type: 'float', nullable: true }),
    __metadata("design:type", Number)
], Canal.prototype, "depthMeters", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'capacity_cms', type: 'float', nullable: true }),
    __metadata("design:type", Number)
], Canal.prototype, "capacityCms", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'geometry',
        spatialFeatureType: 'LineString',
        srid: 4326,
    }),
    __metadata("design:type", Object)
], Canal.prototype, "geometry", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'upstream_node_id', nullable: true }),
    __metadata("design:type", String)
], Canal.prototype, "upstreamNodeId", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'downstream_node_id', nullable: true }),
    __metadata("design:type", String)
], Canal.prototype, "downstreamNodeId", void 0);
__decorate([
    (0, typeorm_1.ManyToOne)(() => zone_entity_1.Zone, (zone) => zone.canals, { nullable: true }),
    __metadata("design:type", zone_entity_1.Zone)
], Canal.prototype, "zone", void 0);
__decorate([
    (0, typeorm_1.OneToMany)(() => gate_entity_1.Gate, (gate) => gate.canal),
    __metadata("design:type", Array)
], Canal.prototype, "gates", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], Canal.prototype, "createdAt", void 0);
__decorate([
    (0, typeorm_1.UpdateDateColumn)({ name: 'updated_at' }),
    __metadata("design:type", Date)
], Canal.prototype, "updatedAt", void 0);
exports.Canal = Canal = __decorate([
    (0, typeorm_1.Entity)('canal_network'),
    (0, typeorm_1.Index)(['canalCode'], { unique: true })
], Canal);
//# sourceMappingURL=canal.entity.js.map