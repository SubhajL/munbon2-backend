import { z } from 'zod';

const polygonSchema = z.object({
  type: z.literal('Polygon'),
  coordinates: z.array(
    z.array(z.tuple([z.number(), z.number()]))
  ).min(1),
});

export const createZoneSchema = z.object({
  body: z.object({
    code: z.string().min(1).max(50),
    name: z.string().min(1).max(200),
    type: z.enum(['irrigation', 'drainage', 'mixed']),
    geometry: polygonSchema,
    waterAllocation: z.number().min(0).optional(),
    description: z.string().optional(),
    metadata: z.record(z.any()).optional(),
  }),
});

export const updateZoneSchema = z.object({
  params: z.object({
    id: z.string().uuid(),
  }),
  body: z.object({
    code: z.string().min(1).max(50).optional(),
    name: z.string().min(1).max(200).optional(),
    type: z.enum(['irrigation', 'drainage', 'mixed']).optional(),
    waterAllocation: z.number().min(0).optional(),
    status: z.enum(['active', 'inactive', 'maintenance']).optional(),
    description: z.string().optional(),
    metadata: z.record(z.any()).optional(),
  }),
});

export const queryZoneSchema = z.object({
  body: z.object({
    type: z.enum(['irrigation', 'drainage', 'mixed']).optional(),
    status: z.enum(['active', 'inactive', 'maintenance']).optional(),
    minArea: z.number().min(0).optional(),
    maxArea: z.number().min(0).optional(),
    bounds: z.tuple([
      z.number(), // minLng
      z.number(), // minLat
      z.number(), // maxLng
      z.number(), // maxLat
    ]).optional(),
    nearPoint: z.object({
      lng: z.number().min(-180).max(180),
      lat: z.number().min(-90).max(90),
      distance: z.number().min(0),
    }).optional(),
  }),
});

export const zoneIdSchema = z.object({
  params: z.object({
    id: z.string().uuid(),
  }),
});