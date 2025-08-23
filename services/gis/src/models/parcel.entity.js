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
exports.Parcel = exports.IrrigationMethod = exports.LandUseType = exports.ParcelStatus = void 0;
const typeorm_1 = require("typeorm");
const zone_entity_1 = require("./zone.entity");
var ParcelStatus;
(function (ParcelStatus) {
    ParcelStatus["ACTIVE"] = "active";
    ParcelStatus["INACTIVE"] = "inactive";
    ParcelStatus["ABANDONED"] = "abandoned";
    ParcelStatus["CONVERTING"] = "converting";
})(ParcelStatus || (exports.ParcelStatus = ParcelStatus = {}));
var LandUseType;
(function (LandUseType) {
    LandUseType["RICE"] = "rice";
    LandUseType["VEGETABLE"] = "vegetable";
    LandUseType["FRUIT"] = "fruit";
    LandUseType["AQUACULTURE"] = "aquaculture";
    LandUseType["LIVESTOCK"] = "livestock";
    LandUseType["MIXED"] = "mixed";
    LandUseType["FALLOW"] = "fallow";
    LandUseType["OTHER"] = "other";
})(LandUseType || (exports.LandUseType = LandUseType = {}));
var IrrigationMethod;
(function (IrrigationMethod) {
    IrrigationMethod["FLOODING"] = "flooding";
    IrrigationMethod["FURROW"] = "furrow";
    IrrigationMethod["SPRINKLER"] = "sprinkler";
    IrrigationMethod["DRIP"] = "drip";
    IrrigationMethod["CENTER_PIVOT"] = "center_pivot";
    IrrigationMethod["MANUAL"] = "manual";
})(IrrigationMethod || (exports.IrrigationMethod = IrrigationMethod = {}));
let Parcel = class Parcel {
    id;
    plotCode;
    farmerId;
    zoneId;
    areaHectares;
    areaRai;
    boundary;
    currentCropType;
    plantingDate;
    expectedHarvestDate;
    soilType;
    properties;
    zone;
    createdAt;
    updatedAt;
    get geoJSON() {
        return {
            type: 'Feature',
            geometry: this.boundary,
            properties: {
                id: this.id,
                plotCode: this.plotCode,
                areaHectares: this.areaHectares,
                currentCropType: this.currentCropType,
                farmerId: this.farmerId,
                soilType: this.soilType,
                plantingDate: this.plantingDate,
                expectedHarvestDate: this.expectedHarvestDate,
            },
        };
    }
};
exports.Parcel = Parcel;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], Parcel.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'plot_code', unique: true }),
    __metadata("design:type", String)
], Parcel.prototype, "plotCode", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'farmer_id' }),
    __metadata("design:type", String)
], Parcel.prototype, "farmerId", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'zone_id' }),
    __metadata("design:type", String)
], Parcel.prototype, "zoneId", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'area_hectares', type: 'float' }),
    __metadata("design:type", Number)
], Parcel.prototype, "areaHectares", void 0);
__decorate([
    (0, typeorm_1.Column)({
        name: 'area_rai',
        type: 'numeric',
        precision: 10,
        scale: 2,
        generatedType: 'STORED',
        asExpression: 'area_hectares * 6.25',
        insert: false,
        update: false
    }),
    __metadata("design:type", Number)
], Parcel.prototype, "areaRai", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'geometry',
        spatialFeatureType: 'Geometry',
        srid: 4326,
    }),
    __metadata("design:type", Object)
], Parcel.prototype, "boundary", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'current_crop_type', nullable: true }),
    __metadata("design:type", String)
], Parcel.prototype, "currentCropType", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'planting_date', nullable: true }),
    __metadata("design:type", Date)
], Parcel.prototype, "plantingDate", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'expected_harvest_date', nullable: true }),
    __metadata("design:type", Date)
], Parcel.prototype, "expectedHarvestDate", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'soil_type', nullable: true }),
    __metadata("design:type", String)
], Parcel.prototype, "soilType", void 0);
__decorate([
    (0, typeorm_1.Column)({
        name: 'properties',
        type: 'jsonb',
        nullable: true,
        comment: 'Additional properties including RID attributes, water demand, etc.'
    }),
    __metadata("design:type", Object)
], Parcel.prototype, "properties", void 0);
__decorate([
    (0, typeorm_1.ManyToOne)(() => zone_entity_1.Zone, (zone) => zone.parcels),
    (0, typeorm_1.JoinColumn)({ name: 'zone_id' }),
    __metadata("design:type", zone_entity_1.Zone)
], Parcel.prototype, "zone", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], Parcel.prototype, "createdAt", void 0);
__decorate([
    (0, typeorm_1.UpdateDateColumn)({ name: 'updated_at' }),
    __metadata("design:type", Date)
], Parcel.prototype, "updatedAt", void 0);
exports.Parcel = Parcel = __decorate([
    (0, typeorm_1.Entity)('agricultural_plots'),
    (0, typeorm_1.Index)(['plotCode'], { unique: true }),
    (0, typeorm_1.Index)(['farmerId']),
    (0, typeorm_1.Index)(['zoneId'])
], Parcel);
//# sourceMappingURL=parcel.entity.js.map