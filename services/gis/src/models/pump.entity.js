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
exports.Pump = exports.PumpStatus = exports.PumpType = void 0;
const typeorm_1 = require("typeorm");
var PumpType;
(function (PumpType) {
    PumpType["CENTRIFUGAL"] = "centrifugal";
    PumpType["SUBMERSIBLE"] = "submersible";
    PumpType["TURBINE"] = "turbine";
    PumpType["AXIAL_FLOW"] = "axial_flow";
    PumpType["MIXED_FLOW"] = "mixed_flow";
})(PumpType || (exports.PumpType = PumpType = {}));
var PumpStatus;
(function (PumpStatus) {
    PumpStatus["OPERATIONAL"] = "operational";
    PumpStatus["STANDBY"] = "standby";
    PumpStatus["MAINTENANCE"] = "maintenance";
    PumpStatus["FAULTY"] = "faulty";
    PumpStatus["DECOMMISSIONED"] = "decommissioned";
})(PumpStatus || (exports.PumpStatus = PumpStatus = {}));
let Pump = class Pump {
    id;
    structureCode;
    structureName;
    structureType;
    canalId;
    location;
    elevationMsl;
    maxDischargeCms;
    scadaTag;
    operationalStatus;
    createdAt;
    updatedAt;
};
exports.Pump = Pump;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], Pump.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'structure_code', unique: true }),
    __metadata("design:type", String)
], Pump.prototype, "structureCode", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'structure_name' }),
    __metadata("design:type", String)
], Pump.prototype, "structureName", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'structure_type' }),
    __metadata("design:type", String)
], Pump.prototype, "structureType", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'canal_id', nullable: true }),
    __metadata("design:type", String)
], Pump.prototype, "canalId", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'geometry',
        spatialFeatureType: 'Point',
        srid: 4326,
    }),
    __metadata("design:type", Object)
], Pump.prototype, "location", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'elevation_msl', type: 'float', nullable: true }),
    __metadata("design:type", Number)
], Pump.prototype, "elevationMsl", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'max_discharge_cms', type: 'float', nullable: true }),
    __metadata("design:type", Number)
], Pump.prototype, "maxDischargeCms", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'scada_tag', nullable: true }),
    __metadata("design:type", String)
], Pump.prototype, "scadaTag", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'operational_status', nullable: true }),
    __metadata("design:type", String)
], Pump.prototype, "operationalStatus", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], Pump.prototype, "createdAt", void 0);
__decorate([
    (0, typeorm_1.UpdateDateColumn)({ name: 'updated_at' }),
    __metadata("design:type", Date)
], Pump.prototype, "updatedAt", void 0);
exports.Pump = Pump = __decorate([
    (0, typeorm_1.Entity)('control_structures'),
    (0, typeorm_1.Index)(['structureCode'], { unique: true })
], Pump);
//# sourceMappingURL=pump.entity.js.map