import { pool } from '@config/database';
import { AreaInfo, AreaType } from '@types/index';
import { logger } from '@utils/logger';

export class AreaService {
  /**
   * Create a new area
   */
  async createArea(area: AreaInfo): Promise<AreaInfo> {
    try {
      const query = `
        INSERT INTO area_info (
          area_id, area_type, area_name, total_area_rai,
          parent_area_id, aos_station, province
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING *
      `;

      const result = await pool.query(query, [
        area.areaId,
        area.areaType,
        area.areaName || null,
        area.totalAreaRai,
        area.parentAreaId || null,
        area.aosStation || 'นครราชสีมา',
        area.province || 'นครราชสีมา',
      ]);

      return this.mapRowToAreaInfo(result.rows[0]);
    } catch (error) {
      logger.error('Failed to create area', error);
      throw error;
    }
  }

  /**
   * Get area by ID
   */
  async getAreaById(areaId: string): Promise<AreaInfo | null> {
    try {
      const query = `SELECT * FROM area_info WHERE area_id = $1`;
      const result = await pool.query(query, [areaId]);

      if (result.rows.length === 0) {
        return null;
      }

      return this.mapRowToAreaInfo(result.rows[0]);
    } catch (error) {
      logger.error('Failed to get area by ID', error);
      throw error;
    }
  }

  /**
   * Get all areas by type
   */
  async getAreasByType(areaType: AreaType): Promise<AreaInfo[]> {
    try {
      const query = `
        SELECT * FROM area_info 
        WHERE area_type = $1 
        ORDER BY area_id
      `;
      const result = await pool.query(query, [areaType]);

      return result.rows.map(row => this.mapRowToAreaInfo(row));
    } catch (error) {
      logger.error('Failed to get areas by type', error);
      throw error;
    }
  }

  /**
   * Get child areas of a parent
   */
  async getChildAreas(parentAreaId: string): Promise<AreaInfo[]> {
    try {
      const query = `
        SELECT * FROM area_info 
        WHERE parent_area_id = $1 
        ORDER BY area_type, area_id
      `;
      const result = await pool.query(query, [parentAreaId]);

      return result.rows.map(row => this.mapRowToAreaInfo(row));
    } catch (error) {
      logger.error('Failed to get child areas', error);
      throw error;
    }
  }

  /**
   * Update area information
   */
  async updateArea(areaId: string, updates: Partial<AreaInfo>): Promise<AreaInfo | null> {
    try {
      const updateFields = [];
      const values = [];
      let paramCount = 1;

      if (updates.areaName !== undefined) {
        updateFields.push(`area_name = $${paramCount++}`);
        values.push(updates.areaName);
      }
      if (updates.totalAreaRai !== undefined) {
        updateFields.push(`total_area_rai = $${paramCount++}`);
        values.push(updates.totalAreaRai);
      }
      if (updates.parentAreaId !== undefined) {
        updateFields.push(`parent_area_id = $${paramCount++}`);
        values.push(updates.parentAreaId);
      }
      if (updates.aosStation !== undefined) {
        updateFields.push(`aos_station = $${paramCount++}`);
        values.push(updates.aosStation);
      }
      if (updates.province !== undefined) {
        updateFields.push(`province = $${paramCount++}`);
        values.push(updates.province);
      }

      if (updateFields.length === 0) {
        return await this.getAreaById(areaId);
      }

      values.push(areaId);
      const query = `
        UPDATE area_info 
        SET ${updateFields.join(', ')}, updated_at = NOW()
        WHERE area_id = $${paramCount}
        RETURNING *
      `;

      const result = await pool.query(query, values);

      if (result.rows.length === 0) {
        return null;
      }

      return this.mapRowToAreaInfo(result.rows[0]);
    } catch (error) {
      logger.error('Failed to update area', error);
      throw error;
    }
  }

  /**
   * Get area hierarchy (project -> zones -> sections)
   */
  async getAreaHierarchy(projectId: string): Promise<any> {
    try {
      // Get project
      const project = await this.getAreaById(projectId);
      if (!project || project.areaType !== 'project') {
        throw new Error('Invalid project ID');
      }

      // Get zones
      const zones = await this.getChildAreas(projectId);
      
      // Get sections for each zone
      const hierarchy = {
        ...project,
        zones: await Promise.all(
          zones.map(async (zone) => ({
            ...zone,
            sections: await this.getChildAreas(zone.areaId),
          }))
        ),
      };

      return hierarchy;
    } catch (error) {
      logger.error('Failed to get area hierarchy', error);
      throw error;
    }
  }

  /**
   * Calculate total area for a parent (sum of child areas)
   */
  async calculateTotalArea(parentAreaId: string): Promise<number> {
    try {
      const query = `
        SELECT SUM(total_area_rai) as total_area
        FROM area_info
        WHERE parent_area_id = $1
      `;

      const result = await pool.query(query, [parentAreaId]);
      return parseFloat(result.rows[0]?.total_area || '0');
    } catch (error) {
      logger.error('Failed to calculate total area', error);
      throw error;
    }
  }

  /**
   * Delete area (cascade to child areas)
   */
  async deleteArea(areaId: string): Promise<boolean> {
    try {
      // First, delete all child areas
      await pool.query(`
        DELETE FROM area_info 
        WHERE parent_area_id = $1
      `, [areaId]);

      // Then delete the area itself
      const result = await pool.query(`
        DELETE FROM area_info 
        WHERE area_id = $1
      `, [areaId]);

      return result.rowCount > 0;
    } catch (error) {
      logger.error('Failed to delete area', error);
      throw error;
    }
  }

  /**
   * Import areas from data
   */
  async importAreas(areas: AreaInfo[]): Promise<{ success: number; failed: number }> {
    let success = 0;
    let failed = 0;

    for (const area of areas) {
      try {
        await this.createArea(area);
        success++;
      } catch (error) {
        logger.error(`Failed to import area ${area.areaId}`, error);
        failed++;
      }
    }

    return { success, failed };
  }

  /**
   * Get area statistics
   */
  async getAreaStatistics(): Promise<{
    totalProjects: number;
    totalZones: number;
    totalSections: number;
    totalAreaRai: number;
  }> {
    try {
      const query = `
        SELECT 
          area_type,
          COUNT(*) as count,
          SUM(total_area_rai) as total_area
        FROM area_info
        GROUP BY area_type
      `;

      const result = await pool.query(query);
      
      const stats = {
        totalProjects: 0,
        totalZones: 0,
        totalSections: 0,
        totalAreaRai: 0,
      };

      for (const row of result.rows) {
        const count = parseInt(row.count);
        const area = parseFloat(row.total_area || '0');
        
        switch (row.area_type) {
          case 'project':
            stats.totalProjects = count;
            break;
          case 'zone':
            stats.totalZones = count;
            break;
          case 'section':
            stats.totalSections = count;
            break;
        }
        
        stats.totalAreaRai += area;
      }

      return stats;
    } catch (error) {
      logger.error('Failed to get area statistics', error);
      throw error;
    }
  }

  /**
   * Map database row to AreaInfo
   */
  private mapRowToAreaInfo(row: any): AreaInfo {
    return {
      areaId: row.area_id,
      areaType: row.area_type,
      areaName: row.area_name,
      totalAreaRai: parseFloat(row.total_area_rai),
      parentAreaId: row.parent_area_id,
      aosStation: row.aos_station,
      province: row.province,
    };
  }
}

export const areaService = new AreaService();