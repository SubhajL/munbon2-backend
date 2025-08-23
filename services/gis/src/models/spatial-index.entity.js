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
exports.SpatialIndex = void 0;
const typeorm_1 = require("typeorm");
let SpatialIndex = class SpatialIndex {
    id;
    entityType;
    entityId;
    bounds;
    tileX;
    tileY;
    zoom;
    minZoom;
    maxZoom;
    createdAt;
};
exports.SpatialIndex = SpatialIndex;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], SpatialIndex.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'entity_type' }),
    __metadata("design:type", String)
], SpatialIndex.prototype, "entityType", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'entity_id' }),
    __metadata("design:type", String)
], SpatialIndex.prototype, "entityId", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'geometry',
        spatialFeatureType: 'Polygon',
        srid: 4326,
    }),
    __metadata("design:type", Object)
], SpatialIndex.prototype, "bounds", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'tile_x', type: 'int' }),
    __metadata("design:type", Number)
], SpatialIndex.prototype, "tileX", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'tile_y', type: 'int' }),
    __metadata("design:type", Number)
], SpatialIndex.prototype, "tileY", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'int' }),
    __metadata("design:type", Number)
], SpatialIndex.prototype, "zoom", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'min_zoom', type: 'int', default: 1 }),
    __metadata("design:type", Number)
], SpatialIndex.prototype, "minZoom", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'max_zoom', type: 'int', default: 18 }),
    __metadata("design:type", Number)
], SpatialIndex.prototype, "maxZoom", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'created_at' }),
    __metadata("design:type", Date)
], SpatialIndex.prototype, "createdAt", void 0);
exports.SpatialIndex = SpatialIndex = __decorate([
    (0, typeorm_1.Entity)('spatial_indexes'),
    (0, typeorm_1.Index)(['entityType', 'entityId'], { unique: true }),
    (0, typeorm_1.Index)(['tileX', 'tileY', 'zoom'])
], SpatialIndex);
//# sourceMappingURL=spatial-index.entity.js.map