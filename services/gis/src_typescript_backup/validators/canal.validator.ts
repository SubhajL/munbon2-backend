import { z } from 'zod';

const lineStringSchema = z.object({
  type: z.literal('LineString'),
  coordinates: z.array(z.tuple([z.number(), z.number()])).min(2),
});

export const createCanalSchema = z.object({
  body: z.object({
    code: z.string().min(1).max(50),
    name: z.string().min(1).max(200),
    type: z.enum(['main', 'secondary', 'tertiary', 'field']),
    level: z.number().int().min(1).max(4),
    geometry: lineStringSchema,
    length: z.number().positive().optional(),
    width: z.number().positive().optional(),
    depth: z.number().positive().optional(),
    capacity: z.number().positive(),
    material: z.string().optional(),
    constructionYear: z.number().int().optional(),
    metadata: z.record(z.any()).optional(),
  }),
});

export const updateCanalSchema = z.object({
  params: z.object({
    id: z.string().uuid(),
  }),
  body: z.object({
    code: z.string().min(1).max(50).optional(),
    name: z.string().min(1).max(200).optional(),
    type: z.enum(['main', 'secondary', 'tertiary', 'field']).optional(),
    status: z.enum(['operational', 'maintenance', 'closed', 'damaged']).optional(),
    capacity: z.number().positive().optional(),
    currentFlow: z.number().min(0).optional(),
    metadata: z.record(z.any()).optional(),
  }),
});

export const queryCanalSchema = z.object({
  body: z.object({
    type: z.enum(['main', 'secondary', 'tertiary', 'field']).optional(),
    level: z.number().int().min(1).max(4).optional(),
    status: z.enum(['operational', 'maintenance', 'closed', 'damaged']).optional(),
    minCapacity: z.number().positive().optional(),
    maxCapacity: z.number().positive().optional(),
    bounds: z.tuple([
      z.number(), // minLng
      z.number(), // minLat
      z.number(), // maxLng
      z.number(), // maxLat
    ]).optional(),
    nearPoint: z.object({
      lng: z.number().min(-180).max(180),
      lat: z.number().min(-90).max(90),
      distance: z.number().positive(),
    }).optional(),
  }),
});

export const canalIdSchema = z.object({
  params: z.object({
    id: z.string().uuid(),
  }),
});

export const flowUpdateSchema = z.object({
  params: z.object({
    id: z.string().uuid(),
  }),
  body: z.object({
    flowRate: z.number().min(0),
    measuredAt: z.string().datetime(),
    sensorId: z.string().optional(),
  }),
});