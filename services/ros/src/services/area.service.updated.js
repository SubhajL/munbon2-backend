"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.areaService = exports.AreaService = void 0;
const database_1 = require("@config/database");
const logger_1 = require("@utils/logger");
const AreaIdFormatter = require("@utils/area-id-formatter");

class AreaService {
    /**
     * Create a new area with PP-ZZ-CC-SS format validation
     */
    async createArea(area) {
        try {
            // Validate area ID format
            if (!AreaIdFormatter.isValidFormat(area.areaId)) {
                throw new Error(`Invalid area ID format: ${area.areaId}. Expected format: PP-ZZ-CC-SS`);
            }

            // Parse components
            const components = AreaIdFormatter.parseAreaId(area.areaId);
            const derivedAreaType = AreaIdFormatter.getAreaType(area.areaId);

            // Validate that provided area type matches derived type
            if (area.areaType && area.areaType !== derivedAreaType) {
                throw new Error(`Area type mismatch. ID format suggests '${derivedAreaType}' but provided type is '${area.areaType}'`);
            }

            // Validate parent-child relationship if parent is provided
            if (area.parentAreaId) {
                const expectedParent = AreaIdFormatter.getParentAreaId(area.areaId);
                if (area.parentAreaId !== expectedParent) {
                    throw new Error(`Invalid parent-child relationship. Expected parent: ${expectedParent}, provided: ${area.parentAreaId}`);
                }
            }

            const query = `
                INSERT INTO area_info (
                    area_id, area_type, area_name, total_area_rai,
                    parent_area_id, aos_station, province,
                    project_code, zone_code, canal_code, section_code
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING *
            `;
            
            const result = await database_1.pool.query(query, [
                area.areaId,
                derivedAreaType,
                area.areaName || null,
                area.totalAreaRai,
                area.parentAreaId || AreaIdFormatter.getParentAreaId(area.areaId),
                area.aosStation || 'นครราชสีมา',
                area.province || 'นครราชสีมา',
                components.projectCode,
                components.zoneCode,
                components.canalCode,
                components.sectionCode
            ]);
            
            return this.mapRowToAreaInfo(result.rows[0]);
        }
        catch (error) {
            logger_1.logger.error('Failed to create area', error);
            throw error;
        }
    }

    /**
     * Get area by ID with format validation
     */
    async getAreaById(areaId) {
        try {
            // Support both old and new formats during migration
            let query;
            let params;

            if (AreaIdFormatter.isValidFormat(areaId)) {
                query = `SELECT * FROM area_info WHERE area_id = $1`;
                params = [areaId];
            } else {
                // Try to find by old ID using mapping table
                query = `
                    SELECT a.* 
                    FROM area_info a
                    JOIN area_id_mapping m ON a.area_id = m.new_area_id
                    WHERE m.old_area_id = $1
                `;
                params = [areaId];
            }

            const result = await database_1.pool.query(query, params);
            
            if (result.rows.length === 0) {
                return null;
            }
            
            return this.mapRowToAreaInfo(result.rows[0]);
        }
        catch (error) {
            logger_1.logger.error('Failed to get area by ID', error);
            throw error;
        }
    }

    /**
     * Get areas by components (project, zone, canal)
     */
    async getAreasByComponents(projectCode, zoneCode = null, canalCode = null) {
        try {
            let query = `SELECT * FROM area_info WHERE project_code = $1`;
            const params = [projectCode];

            if (zoneCode) {
                query += ` AND zone_code = $${params.length + 1}`;
                params.push(zoneCode);
            }

            if (canalCode) {
                query += ` AND canal_code = $${params.length + 1}`;
                params.push(canalCode);
            }

            query += ` ORDER BY zone_code, canal_code, section_code`;

            const result = await database_1.pool.query(query, params);
            return result.rows.map(row => this.mapRowToAreaInfo(row));
        }
        catch (error) {
            logger_1.logger.error('Failed to get areas by components', error);
            throw error;
        }
    }

    /**
     * Get complete area hierarchy for a given area ID
     */
    async getAreaHierarchyPath(areaId) {
        try {
            const ancestorIds = AreaIdFormatter.getAncestorAreaIds(areaId);
            
            const query = `
                SELECT * FROM area_info 
                WHERE area_id = ANY($1::varchar[])
                ORDER BY 
                    CASE area_type
                        WHEN 'project' THEN 1
                        WHEN 'zone' THEN 2
                        WHEN 'canal' THEN 3
                        WHEN 'section' THEN 4
                    END
            `;

            const result = await database_1.pool.query(query, [ancestorIds]);
            return result.rows.map(row => this.mapRowToAreaInfo(row));
        }
        catch (error) {
            logger_1.logger.error('Failed to get area hierarchy path', error);
            throw error;
        }
    }

    /**
     * Search areas with flexible pattern matching
     */
    async searchAreas(searchTerm, areaType = null) {
        try {
            let query = `
                SELECT * FROM area_info 
                WHERE (
                    area_id ILIKE $1 
                    OR area_name ILIKE $1
                    OR old_area_id ILIKE $1
                )
            `;
            const params = [`%${searchTerm}%`];

            if (areaType) {
                query += ` AND area_type = $2`;
                params.push(areaType);
            }

            query += ` ORDER BY area_id`;

            const result = await database_1.pool.query(query, params);
            return result.rows.map(row => this.mapRowToAreaInfo(row));
        }
        catch (error) {
            logger_1.logger.error('Failed to search areas', error);
            throw error;
        }
    }

    /**
     * Migrate old area IDs to new format
     */
    async migrateAreaId(oldAreaId, areaType, projectCode = '01') {
        try {
            const newAreaId = AreaIdFormatter.convertFromOldFormat(oldAreaId, areaType, projectCode);
            
            if (!newAreaId) {
                throw new Error(`Cannot convert area ID: ${oldAreaId}`);
            }

            // Update the area_info table
            const updateQuery = `
                UPDATE area_info 
                SET area_id = $1,
                    old_area_id = $2,
                    project_code = $3,
                    zone_code = $4,
                    canal_code = $5,
                    section_code = $6,
                    updated_at = NOW()
                WHERE area_id = $2
                RETURNING *
            `;

            const components = AreaIdFormatter.parseAreaId(newAreaId);
            
            const result = await database_1.pool.query(updateQuery, [
                newAreaId,
                oldAreaId,
                components.projectCode,
                components.zoneCode,
                components.canalCode,
                components.sectionCode
            ]);

            if (result.rows.length === 0) {
                throw new Error(`Area not found: ${oldAreaId}`);
            }

            // Update mapping table
            await database_1.pool.query(`
                INSERT INTO area_id_mapping (old_area_id, new_area_id, area_type, project_code, zone_code, canal_code, section_code)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (old_area_id) 
                DO UPDATE SET new_area_id = $2, updated_at = NOW()
            `, [oldAreaId, newAreaId, areaType, components.projectCode, components.zoneCode, components.canalCode, components.sectionCode]);

            return this.mapRowToAreaInfo(result.rows[0]);
        }
        catch (error) {
            logger_1.logger.error('Failed to migrate area ID', error);
            throw error;
        }
    }

    /**
     * Get area statistics with new format
     */
    async getAreaStatisticsByProject(projectCode = '01') {
        try {
            const query = `
                SELECT 
                    area_type,
                    COUNT(*) as count,
                    SUM(total_area_rai) as total_area,
                    COUNT(DISTINCT zone_code) FILTER (WHERE zone_code != '00') as zone_count,
                    COUNT(DISTINCT canal_code) FILTER (WHERE canal_code != '00') as canal_count,
                    COUNT(DISTINCT section_code) FILTER (WHERE section_code != '00') as section_count
                FROM area_info
                WHERE project_code = $1
                GROUP BY area_type
            `;
            
            const result = await database_1.pool.query(query, [projectCode]);
            
            const stats = {
                projectCode,
                totalProjects: 0,
                totalZones: 0,
                totalCanals: 0,
                totalSections: 0,
                totalAreaRai: 0,
                byType: {}
            };
            
            for (const row of result.rows) {
                const count = parseInt(row.count);
                const area = parseFloat(row.total_area || '0');
                
                stats.byType[row.area_type] = {
                    count,
                    totalArea: area
                };
                
                switch (row.area_type) {
                    case 'project':
                        stats.totalProjects = count;
                        break;
                    case 'zone':
                        stats.totalZones = count;
                        break;
                    case 'canal':
                        stats.totalCanals = count;
                        break;
                    case 'section':
                        stats.totalSections = count;
                        break;
                }
                
                stats.totalAreaRai += area;
            }
            
            return stats;
        }
        catch (error) {
            logger_1.logger.error('Failed to get area statistics', error);
            throw error;
        }
    }

    /**
     * Map database row to AreaInfo with components
     */
    mapRowToAreaInfo(row) {
        return {
            areaId: row.area_id,
            areaType: row.area_type,
            areaName: row.area_name,
            totalAreaRai: parseFloat(row.total_area_rai),
            parentAreaId: row.parent_area_id,
            aosStation: row.aos_station,
            province: row.province,
            projectCode: row.project_code,
            zoneCode: row.zone_code,
            canalCode: row.canal_code,
            sectionCode: row.section_code,
            oldAreaId: row.old_area_id,
            formattedDisplay: AreaIdFormatter.formatForDisplay(row.area_id, true)
        };
    }
}

exports.AreaService = AreaService;
exports.areaService = new AreaService();