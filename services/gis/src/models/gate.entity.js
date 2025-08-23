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
exports.Gate = exports.GateControlType = exports.GateStatus = exports.GateType = void 0;
const typeorm_1 = require("typeorm");
const canal_entity_1 = require("./canal.entity");
var GateType;
(function (GateType) {
    GateType["MAIN"] = "main";
    GateType["CHECK"] = "check";
    GateType["FARM"] = "farm";
    GateType["REGULATOR"] = "regulator";
    GateType["SPILLWAY"] = "spillway";
    GateType["INTAKE"] = "intake";
})(GateType || (exports.GateType = GateType = {}));
var GateStatus;
(function (GateStatus) {
    GateStatus["OPERATIONAL"] = "operational";
    GateStatus["MAINTENANCE"] = "maintenance";
    GateStatus["FAULTY"] = "faulty";
    GateStatus["CLOSED"] = "closed";
})(GateStatus || (exports.GateStatus = GateStatus = {}));
var GateControlType;
(function (GateControlType) {
    GateControlType["MANUAL"] = "manual";
    GateControlType["ELECTRIC"] = "electric";
    GateControlType["HYDRAULIC"] = "hydraulic";
    GateControlType["PNEUMATIC"] = "pneumatic";
    GateControlType["SCADA"] = "scada";
})(GateControlType || (exports.GateControlType = GateControlType = {}));
let Gate = class Gate {
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
    canal;
    createdAt;
    updatedAt;
    get geoJSON() {
        return {
            type: 'Feature',
            geometry: this.location,
            properties: {
                id: this.id,
                structureCode: this.structureCode,
                structureName: this.structureName,
                structureType: this.structureType,
                elevationMsl: this.elevationMsl,
                maxDischargeCms: this.maxDischargeCms,
                scadaTag: this.scadaTag,
                operationalStatus: this.operationalStatus,
            },
        };
    }
};
exports.Gate = Gate;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], Gate.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'structure_code', unique: true }),
    __metadata("design:type", String)
], Gate.prototype, "structureCode", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'structure_name' }),
    __metadata("design:type", String)
], Gate.prototype, "structureName", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'structure_type' }),
    __metadata("design:type", String)
], Gate.prototype, "structureType", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'canal_id', nullable: true }),
    __metadata("design:type", String)
], Gate.prototype, "canalId", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'geometry',
        spatialFeatureType: 'Point',
        srid: 4326,
    }),
    __metadata("design:type", Object)
], Gate.prototype, "location", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'elevation_msl', type: 'float', nullable: true }),
    __metadata("design:type", Number)
], Gate.prototype, "elevationMsl", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'max_discharge_cms', type: 'float', nullable: true }),
    __metadata("design:type", Number)
], Gate.prototype, "maxDischargeCms", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'scada_tag', nullable: true }),
    __metadata("design:type", String)
], Gate.prototype, "scadaTag", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'operational_status', nullable: true }),
    __metadata("design:type", String)
], Gate.prototype, "operationalStatus", void 0);
__decorate([
    (0, typeorm_1.ManyToOne)(() => canal_entity_1.Canal, (canal) => canal.gates, { nullable: true }),
    (0, typeorm_1.JoinColumn)({ name: 'canal_id' }),
    __metadata("design:type", canal_entity_1.Canal)
], Gate.prototype, "canal", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], Gate.prototype, "createdAt", void 0);
__decorate([
    (0, typeorm_1.UpdateDateColumn)({ name: 'updated_at' }),
    __metadata("design:type", Date)
], Gate.prototype, "updatedAt", void 0);
exports.Gate = Gate = __decorate([
    (0, typeorm_1.Entity)('control_structures'),
    (0, typeorm_1.Index)(['structureCode'], { unique: true })
], Gate);
//# sourceMappingURL=gate.entity.js.map