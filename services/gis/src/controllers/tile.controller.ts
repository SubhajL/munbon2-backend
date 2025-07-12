import { Request, Response, NextFunction } from 'express';
import { tileService } from '../services/tile.service';
import { logger } from '../utils/logger';
import { ApiError } from '../utils/api-error';
import { config } from '../config';

class TileController {
  async getTile(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { layer, z, x, y } = req.params;

      const tile = await tileService.getTile({
        z: Number(z),
        x: Number(x),
        y: Number(y),
        layer,
      });

      if (tile.length === 0) {
        res.status(204).end(); // No content
        return;
      }

      res.setHeader('Content-Type', 'application/x-protobuf');
      res.setHeader('Content-Encoding', 'gzip');
      res.setHeader('Access-Control-Allow-Origin', '*');
      res.send(tile);
    } catch (error) {
      next(error);
    }
  }

  async getTileMetadata(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { layer } = req.params;

      const metadata = {
        name: layer,
        format: 'pbf',
        bounds: config.tiles.bounds,
        minzoom: config.tiles.minZoom,
        maxzoom: config.tiles.maxZoom,
        attribution: config.tiles.attribution,
        description: this.getLayerDescription(layer),
        fields: this.getLayerFields(layer),
      };

      res.json({
        success: true,
        data: metadata,
      });
    } catch (error) {
      next(error);
    }
  }

  async getAvailableLayers(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const layers = [
        {
          id: 'zones',
          name: 'Irrigation Zones',
          type: 'polygon',
          minZoom: 8,
          maxZoom: 18,
          fields: ['id', 'code', 'name', 'type', 'area', 'status'],
        },
        {
          id: 'parcels',
          name: 'Land Parcels',
          type: 'polygon',
          minZoom: 12,
          maxZoom: 20,
          fields: ['id', 'parcel_code', 'area', 'land_use_type', 'owner_name', 'irrigation_status'],
        },
        {
          id: 'canals',
          name: 'Canal Network',
          type: 'line',
          minZoom: 10,
          maxZoom: 20,
          fields: ['id', 'code', 'name', 'type', 'level', 'status', 'capacity'],
        },
        {
          id: 'gates',
          name: 'Water Gates',
          type: 'point',
          minZoom: 12,
          maxZoom: 20,
          fields: ['id', 'code', 'name', 'type', 'status', 'opening_percentage'],
        },
        {
          id: 'pumps',
          name: 'Pump Stations',
          type: 'point',
          minZoom: 12,
          maxZoom: 20,
          fields: ['id', 'code', 'name', 'type', 'status', 'capacity', 'power'],
        },
      ];

      res.json({
        success: true,
        data: layers,
      });
    } catch (error) {
      next(error);
    }
  }

  async getStyle(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { style } = req.params;
      const baseUrl = `${req.protocol}://${req.get('host')}`;

      const styleJson = {
        version: 8,
        name: `Munbon ${style}`,
        sources: {
          munbon: {
            type: 'vector',
            tiles: [`${baseUrl}/api/v1/tiles/{z}/{x}/{y}.pbf`],
            minzoom: config.tiles.minZoom,
            maxzoom: config.tiles.maxZoom,
          },
        },
        layers: this.getStyleLayers(style),
      };

      res.json(styleJson);
    } catch (error) {
      next(error);
    }
  }

  async clearTileCache(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { layer } = req.params;
      
      await tileService.clearTileCache(layer);

      res.json({
        success: true,
        message: layer ? `Cache cleared for layer: ${layer}` : 'All tile cache cleared',
      });
    } catch (error) {
      next(error);
    }
  }

  async preGenerateTiles(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { layer, minZoom, maxZoom, bounds } = req.body;

      // This would typically queue a background job
      const jobId = `tile-gen-${Date.now()}`;
      
      // In production, this would be handled by a job queue
      setTimeout(() => {
        tileService.preGenerateTiles(layer, minZoom, maxZoom, bounds)
          .catch(error => logger.error('Tile generation error:', error));
      }, 0);

      res.json({
        success: true,
        data: {
          jobId,
          status: 'queued',
          layer,
          zoomRange: { min: minZoom, max: maxZoom },
        },
        message: 'Tile generation job queued',
      });
    } catch (error) {
      next(error);
    }
  }

  async getGenerationStatus(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { jobId } = req.params;

      // In production, this would check actual job status
      const status = {
        jobId,
        status: 'in_progress',
        progress: 45,
        tilesGenerated: 1250,
        totalTiles: 2800,
        startedAt: new Date(Date.now() - 300000), // 5 minutes ago
        estimatedCompletion: new Date(Date.now() + 300000), // 5 minutes from now
      };

      res.json({
        success: true,
        data: status,
      });
    } catch (error) {
      next(error);
    }
  }

  async updateLayerConfig(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { layer } = req.params;
      const config = req.body;

      // In production, this would update layer configuration
      res.json({
        success: true,
        data: {
          layer,
          config,
        },
        message: 'Layer configuration updated',
      });
    } catch (error) {
      next(error);
    }
  }

  private getLayerDescription(layer: string): string {
    const descriptions: Record<string, string> = {
      zones: 'Irrigation zones with water allocation information',
      parcels: 'Individual land parcels with ownership and crop data',
      canals: 'Water distribution canal network',
      gates: 'Water control gates for irrigation management',
      pumps: 'Pump stations for water distribution',
    };
    return descriptions[layer] || 'Unknown layer';
  }

  private getLayerFields(layer: string): Record<string, string> {
    const fields: Record<string, Record<string, string>> = {
      zones: {
        id: 'Unique identifier',
        code: 'Zone code',
        name: 'Zone name',
        type: 'Zone type (irrigation, drainage, mixed)',
        area: 'Total area in hectares',
        status: 'Operational status',
      },
      parcels: {
        id: 'Unique identifier',
        parcel_code: 'Parcel registration code',
        area: 'Parcel area in hectares',
        land_use_type: 'Current land use',
        owner_name: 'Owner name',
        irrigation_status: 'Irrigation availability',
      },
      canals: {
        id: 'Unique identifier',
        code: 'Canal code',
        name: 'Canal name',
        type: 'Canal type (main, secondary, tertiary)',
        level: 'Canal hierarchy level',
        status: 'Operational status',
        capacity: 'Flow capacity in m³/s',
      },
      gates: {
        id: 'Unique identifier',
        code: 'Gate code',
        name: 'Gate name',
        type: 'Gate type',
        status: 'Operational status',
        opening_percentage: 'Current opening percentage',
      },
      pumps: {
        id: 'Unique identifier',
        code: 'Pump code',
        name: 'Pump station name',
        type: 'Pump type',
        status: 'Operational status',
        capacity: 'Pumping capacity in m³/s',
        power: 'Power rating in kW',
      },
    };
    return fields[layer] || {};
  }

  private getStyleLayers(style: string): any[] {
    // Basic style layers for visualization
    return [
      {
        id: 'zones-fill',
        type: 'fill',
        source: 'munbon',
        'source-layer': 'zones',
        paint: {
          'fill-color': '#729fcf',
          'fill-opacity': 0.3,
        },
      },
      {
        id: 'zones-outline',
        type: 'line',
        source: 'munbon',
        'source-layer': 'zones',
        paint: {
          'line-color': '#3465a4',
          'line-width': 2,
        },
      },
      {
        id: 'canals',
        type: 'line',
        source: 'munbon',
        'source-layer': 'canals',
        paint: {
          'line-color': '#204a87',
          'line-width': {
            property: 'level',
            stops: [[1, 3], [2, 2], [3, 1]],
          },
        },
      },
      {
        id: 'gates',
        type: 'circle',
        source: 'munbon',
        'source-layer': 'gates',
        paint: {
          'circle-radius': 6,
          'circle-color': '#ef2929',
          'circle-stroke-color': '#a40000',
          'circle-stroke-width': 2,
        },
      },
      {
        id: 'pumps',
        type: 'circle',
        source: 'munbon',
        'source-layer': 'pumps',
        paint: {
          'circle-radius': 8,
          'circle-color': '#73d216',
          'circle-stroke-color': '#4e9a06',
          'circle-stroke-width': 2,
        },
      },
    ];
  }
}

export const tileController = new TileController();