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
exports.ShapeFileUpload = exports.UploadStatus = void 0;
const typeorm_1 = require("typeorm");
var UploadStatus;
(function (UploadStatus) {
    UploadStatus["PENDING"] = "pending";
    UploadStatus["PROCESSING"] = "processing";
    UploadStatus["COMPLETED"] = "completed";
    UploadStatus["FAILED"] = "failed";
})(UploadStatus || (exports.UploadStatus = UploadStatus = {}));
let ShapeFileUpload = class ShapeFileUpload {
    id;
    uploadId;
    fileName;
    s3Key;
    status;
    metadata;
    error;
    parcelCount;
    uploadedAt;
    updatedAt;
    completedAt;
};
exports.ShapeFileUpload = ShapeFileUpload;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)('uuid'),
    __metadata("design:type", String)
], ShapeFileUpload.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'upload_id', unique: true }),
    __metadata("design:type", String)
], ShapeFileUpload.prototype, "uploadId", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'file_name' }),
    __metadata("design:type", String)
], ShapeFileUpload.prototype, "fileName", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 's3_key' }),
    __metadata("design:type", String)
], ShapeFileUpload.prototype, "s3Key", void 0);
__decorate([
    (0, typeorm_1.Column)({
        type: 'enum',
        enum: UploadStatus,
        default: UploadStatus.PENDING,
    }),
    __metadata("design:type", String)
], ShapeFileUpload.prototype, "status", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: 'jsonb', nullable: true }),
    __metadata("design:type", Object)
], ShapeFileUpload.prototype, "metadata", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true }),
    __metadata("design:type", String)
], ShapeFileUpload.prototype, "error", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'parcel_count', nullable: true }),
    __metadata("design:type", Number)
], ShapeFileUpload.prototype, "parcelCount", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)({ name: 'uploaded_at' }),
    __metadata("design:type", Date)
], ShapeFileUpload.prototype, "uploadedAt", void 0);
__decorate([
    (0, typeorm_1.UpdateDateColumn)({ name: 'updated_at' }),
    __metadata("design:type", Date)
], ShapeFileUpload.prototype, "updatedAt", void 0);
__decorate([
    (0, typeorm_1.Column)({ name: 'completed_at', nullable: true }),
    __metadata("design:type", Date)
], ShapeFileUpload.prototype, "completedAt", void 0);
exports.ShapeFileUpload = ShapeFileUpload = __decorate([
    (0, typeorm_1.Entity)('shape_file_uploads')
], ShapeFileUpload);
//# sourceMappingURL=shape-file-upload.entity.js.map