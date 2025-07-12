import { z } from 'zod';

export const tileRequestSchema = z.object({
  params: z.object({
    layer: z.enum(['zones', 'parcels', 'canals', 'gates', 'pumps']),
    z: z.string().transform(val => parseInt(val, 10)).pipe(z.number().int().min(0).max(20)),
    x: z.string().transform(val => parseInt(val, 10)).pipe(z.number().int().min(0)),
    y: z.string().transform(val => parseInt(val, 10)).pipe(z.number().int().min(0)),
  }),
});