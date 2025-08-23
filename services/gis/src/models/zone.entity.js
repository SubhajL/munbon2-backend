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
exports.Zone = exports.ZoneStatus = exports.ZoneType = void 0;
const typeorm_1 = require("typeorm");
const parcel_entity_1 = require("./parcel.entity");
const canal_entity_1 = require("./canal.entity");
const irrigation_block_entity_1 = require("./irrigation-block.entity");
var ZoneType;
(function (ZoneType) {
    ZoneType["IRRIGATION"] = "irrigation";
    ZoneType["ADMINISTRATIVE"] = "administrative";
    ZoneType["WATERSHED"] = "watershed";
    ZoneType["CULTIVATION"] = "cultivation";
})(ZoneType || (exports.ZoneType = ZoneType = {}));
var ZoneStatus;
(function (ZoneStatus) {
    ZoneStatus["ACTIVE"] = "active";
    ZoneStatus["INACTIVE"] = "inactive";
    ZoneStatus["MAINTENANCE"] = "maintenance";
})(ZoneStatus || (exports.ZoneStatus = ZoneStatus = {}));
let Zone = class Zone {
    id;
    zoneCode;
    zoneName;
    zoneType;
    areaHectares;
    boundary;
    parcels;
    canals;
    irrigationBlocks;
    createdAt;
    updatedAt;
    get geoJSON() {
        return {
            type: 'Feature',
            geometry: this.boundary,
            properties: {
                id: this.id,
                zoneCode: this.zoneCode,
                zoneName: this.zoneName,
                zoneType: this.zoneType,
                areaHectares: this.areaHectares,
            },
        };
    }
};
exports.Zone = Zone;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], Zone.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'zone_code', unique: true }),
    __metadata("design:type", String)
], Zone.prototype, "zoneCode", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'zone_name' }),
    __metadata("design:type", String)
], Zone.prototype, "zoneName", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'zone_type', nullable: true }),
    __metadata("design:type", String)
], Zone.prototype, "zoneType", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'area_hectares', type: 'float' }),
    __metadata("design:type", Number)
], Zone.prototype, "areaHectares", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'geometry',
        spatialFeatureType: 'Polygon',
        srid: 4326,
    }),
    __metadata("design:type", Object)
], Zone.prototype, "boundary", void 0);
__decorate([
    (0, typeorm_1.OneToMany)(() => parcel_entity_1.Parcel, (parcel) => parcel.zone),
    __metadata("design:type", Array)
], Zone.prototype, "parcels", void 0);
__decorate([
    (0, typeorm_1.OneToMany)(() => canal_entity_1.Canal, (canal) => canal.zone),
    __metadata("design:type", Array)
], Zone.prototype, "canals", void 0);
__decorate([
    (0, typeorm_1.OneToMany)(() => irrigation_block_entity_1.IrrigationBlock, (block) => block.zone),
    __metadata("design:type", Array)
], Zone.prototype, "irrigationBlocks", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], Zone.prototype, "createdAt", void 0);
__decorate([
    (0, typeorm_1.UpdateDateColumn)({ name: 'updated_at' }),
    __metadata("design:type", Date)
], Zone.prototype, "updatedAt", void 0);
exports.Zone = Zone = __decorate([
    (0, typeorm_1.Entity)('irrigation_zones'),
    (0, typeorm_1.Index)(['zoneCode'], { unique: true })
], Zone);
//# sourceMappingURL=zone.entity.js.map