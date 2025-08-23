import { z } from 'zod';

const polygonSchema = z.object({
  type: z.literal('Polygon'),
  coordinates: z.array(
    z.array(z.tuple([z.number(), z.number()]))
  ).min(1),
});

export const createParcelSchema = z.object({
  body: z.object({
    parcelCode: z.string().min(1).max(100),
    area: z.number().positive(),
    geometry: polygonSchema,
    zoneId: z.string().uuid(),
    landUseType: z.string().min(1).max(100),
    soilType: z.string().optional(),
    ownerName: z.string().min(1).max(200),
    ownerContact: z.string().optional(),
    irrigationStatus: z.enum(['irrigated', 'non-irrigated', 'partial']),
    waterRights: z.number().min(0).optional(),
    metadata: z.record(z.any()).optional(),
  }),
});

export const updateParcelSchema = z.object({
  params: z.object({
    id: z.string().uuid(),
  }),
  body: z.object({
    parcelCode: z.string().min(1).max(100).optional(),
    area: z.number().positive().optional(),
    landUseType: z.string().min(1).max(100).optional(),
    soilType: z.string().optional(),
    ownerName: z.string().min(1).max(200).optional(),
    ownerContact: z.string().optional(),
    irrigationStatus: z.enum(['irrigated', 'non-irrigated', 'partial']).optional(),
    waterRights: z.number().min(0).optional(),
    metadata: z.record(z.any()).optional(),
  }),
});

export const queryParcelSchema = z.object({
  body: z.object({
    zoneId: z.string().uuid().optional(),
    landUseType: z.string().optional(),
    irrigationStatus: z.enum(['irrigated', 'non-irrigated', 'partial']).optional(),
    ownerName: z.string().optional(),
    minArea: z.number().positive().optional(),
    maxArea: z.number().positive().optional(),
    bounds: z.tuple([
      z.number(), // minLng
      z.number(), // minLat
      z.number(), // maxLng
      z.number(), // maxLat
    ]).optional(),
  }),
});

export const parcelIdSchema = z.object({
  params: z.object({
    id: z.string().uuid(),
  }),
});

export const transferOwnershipSchema = z.object({
  params: z.object({
    id: z.string().uuid(),
  }),
  body: z.object({
    newOwnerId: z.string().uuid(),
    transferDate: z.string().datetime(),
    notes: z.string().optional(),
  }),
});