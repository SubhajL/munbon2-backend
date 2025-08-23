import { z } from 'zod';

const pointSchema = z.object({
  type: z.literal('Point'),
  coordinates: z.tuple([z.number(), z.number()]),
});

const lineStringSchema = z.object({
  type: z.literal('LineString'),
  coordinates: z.array(z.tuple([z.number(), z.number()])).min(2),
});

const polygonSchema = z.object({
  type: z.literal('Polygon'),
  coordinates: z.array(
    z.array(z.tuple([z.number(), z.number()]))
  ).min(1),
});

const geometrySchema = z.union([pointSchema, lineStringSchema, polygonSchema]);

export const spatialQuerySchema = z.object({
  body: z.object({
    tableName: z.string().min(1),
    bounds: z.tuple([
      z.number(), // minLng
      z.number(), // minLat
      z.number(), // maxLng
      z.number(), // maxLat
    ]).optional(),
    center: z.tuple([z.number(), z.number()]).optional(),
    distance: z.number().positive().optional(),
    unit: z.enum(['meters', 'kilometers', 'miles', 'feet']).optional(),
    geometry: geometrySchema.optional(),
    properties: z.array(z.string()).optional(),
  }),
});

export const bufferSchema = z.object({
  body: z.object({
    geometry: geometrySchema,
    distance: z.number().positive(),
    unit: z.enum(['meters', 'kilometers', 'miles', 'feet']).optional(),
    options: z.object({
      steps: z.number().int().positive().optional(),
      units: z.string().optional(),
    }).optional(),
  }),
});

export const unionSchema = z.object({
  body: z.object({
    geometries: z.array(geometrySchema).min(2),
  }),
});

export const intersectionSchema = z.object({
  body: z.object({
    geometry1: geometrySchema,
    geometry2: geometrySchema,
  }),
});