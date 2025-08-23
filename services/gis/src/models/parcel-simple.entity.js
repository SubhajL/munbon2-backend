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
exports.ParcelSimple = exports.LandUseType = exports.ParcelStatus = void 0;
const typeorm_1 = require("typeorm");
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
let ParcelSimple = class ParcelSimple {
    id;
    parcelCode;
    uploadId;
    zoneId;
    geometry;
    centroid;
    area;
    perimeter;
    status;
    landUseType;
    ownerId;
    ownerName;
    cropType;
    attributes;
    properties;
    createdAt;
    updatedAt;
};
exports.ParcelSimple = ParcelSimple;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], ParcelSimple.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'parcel_code', unique: true }),
    __metadata("design:type", String)
], ParcelSimple.prototype, "parcelCode", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'upload_id' }),
    __metadata("design:type", String)
], ParcelSimple.prototype, "uploadId", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'zone_id' }),
    __metadata("design:type", String)
], ParcelSimple.prototype, "zoneId", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'jsonb' }),
    __metadata("design:type", Object)
], ParcelSimple.prototype, "geometry", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'jsonb', nullable: true }),
    __metadata("design:type", Object)
], ParcelSimple.prototype, "centroid", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'float' }),
    __metadata("design:type", Number)
], ParcelSimple.prototype, "area", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'float', nullable: true }),
    __metadata("design:type", Number)
], ParcelSimple.prototype, "perimeter", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'enum',
        enum: ParcelStatus,
        default: ParcelStatus.ACTIVE,
    }),
    __metadata("design:type", String)
], ParcelSimple.prototype, "status", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'enum',
        enum: LandUseType,
        default: LandUseType.RICE,
        name: 'land_use_type',
    }),
    __metadata("design:type", String)
], ParcelSimple.prototype, "landUseType", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'owner_id', nullable: true }),
    __metadata("design:type", String)
], ParcelSimple.prototype, "ownerId", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'owner_name', nullable: true }),
    __metadata("design:type", String)
], ParcelSimple.prototype, "ownerName", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'crop_type', nullable: true }),
    __metadata("design:type", String)
], ParcelSimple.prototype, "cropType", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'jsonb', nullable: true }),
    __metadata("design:type", Object)
], ParcelSimple.prototype, "attributes", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'jsonb', nullable: true }),
    __metadata("design:type", Object)
], ParcelSimple.prototype, "properties", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], ParcelSimple.prototype, "createdAt", void 0);
__decorate([
    (0, typeorm_1.UpdateDateColumn)({ name: 'updated_at' }),
    __metadata("design:type", Date)
], ParcelSimple.prototype, "updatedAt", void 0);
exports.ParcelSimple = ParcelSimple = __decorate([
    (0, typeorm_1.Entity)('parcels_simple'),
    (0, typeorm_1.Index)(['parcelCode'], { unique: true }),
    (0, typeorm_1.Index)(['ownerId']),
    (0, typeorm_1.Index)(['zoneId']),
    (0, typeorm_1.Index)(['uploadId'])
], ParcelSimple);
//# sourceMappingURL=parcel-simple.entity.js.map