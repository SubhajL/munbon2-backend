/**
 * Schema helper utilities for AWD Control Service
 * Helps manage schema-prefixed queries when using consolidated database
 */

export class SchemaHelper {
  private postgresSchema: string;
  private timescaleSchema: string;
  private gisSchema: string;

  constructor() {
    this.postgresSchema = process.env.POSTGRES_SCHEMA || 'awd';
    this.timescaleSchema = process.env.TIMESCALE_SCHEMA || 'public';
    this.gisSchema = 'gis'; // GIS schema is always in the same database
  }

  /**
   * Prefix table name with appropriate schema
   */
  public prefixTable(tableName: string, schemaType: 'postgres' | 'timescale' | 'gis' = 'postgres'): string {
    switch (schemaType) {
      case 'postgres':
        return `${this.postgresSchema}.${tableName}`;
      case 'timescale':
        return `${this.timescaleSchema}.${tableName}`;
      case 'gis':
        return `${this.gisSchema}.${tableName}`;
      default:
        return tableName;
    }
  }

  /**
   * Get table name based on original database
   */
  public getTableName(originalTable: string): string {
    // Map tables to their appropriate schemas
    const tableSchemaMap: Record<string, { table: string, schema: 'postgres' | 'timescale' | 'gis' }> = {
      // PostgreSQL tables (AWD schema)
      'awd_fields': { table: 'awd_fields', schema: 'postgres' },
      'awd_configurations': { table: 'awd_configurations', schema: 'postgres' },
      'awd_sensors': { table: 'awd_sensors', schema: 'postgres' },
      'irrigation_schedules': { table: 'irrigation_schedules', schema: 'postgres' },
      'awd_field_cycles': { table: 'awd_field_cycles', schema: 'postgres' },
      
      // GIS tables (remain in GIS schema)
      'gis.water_level_measurements': { table: 'water_level_measurements', schema: 'gis' },
      'gis.field_attributes': { table: 'field_attributes', schema: 'gis' },
      
      // TimescaleDB tables
      'awd_sensor_readings': { table: 'awd_sensor_readings', schema: 'timescale' },
      'irrigation_events': { table: 'irrigation_events', schema: 'timescale' },
      'water_level_readings': { table: 'water_level_readings', schema: 'timescale' },
      'moisture_readings': { table: 'moisture_readings', schema: 'timescale' },
    };

    const mapping = tableSchemaMap[originalTable];
    if (mapping) {
      return this.prefixTable(mapping.table, mapping.schema);
    }

    // Default: assume it's in AWD schema
    return this.prefixTable(originalTable, 'postgres');
  }

  /**
   * Convert a query to use proper schema prefixes
   */
  public convertQuery(query: string): string {
    // Replace common table references
    let convertedQuery = query;

    // AWD tables
    convertedQuery = convertedQuery.replace(/\bawd_fields\b/g, this.getTableName('awd_fields'));
    convertedQuery = convertedQuery.replace(/\bawd_configurations\b/g, this.getTableName('awd_configurations'));
    convertedQuery = convertedQuery.replace(/\bawd_sensors\b/g, this.getTableName('awd_sensors'));
    convertedQuery = convertedQuery.replace(/\birrigation_schedules\b/g, this.getTableName('irrigation_schedules'));
    convertedQuery = convertedQuery.replace(/\bawd_field_cycles\b/g, this.getTableName('awd_field_cycles'));

    // TimescaleDB tables
    convertedQuery = convertedQuery.replace(/\bawd_sensor_readings\b/g, this.getTableName('awd_sensor_readings'));
    convertedQuery = convertedQuery.replace(/\birrigation_events\b/g, this.getTableName('irrigation_events'));
    convertedQuery = convertedQuery.replace(/\bwater_level_readings\b/g, this.getTableName('water_level_readings'));
    convertedQuery = convertedQuery.replace(/\bmoisture_readings\b/g, this.getTableName('moisture_readings'));

    // GIS tables (already prefixed in most queries)
    convertedQuery = convertedQuery.replace(/\bgis\.water_level_measurements\b/g, this.getTableName('gis.water_level_measurements'));
    convertedQuery = convertedQuery.replace(/\bgis\.field_attributes\b/g, this.getTableName('gis.field_attributes'));

    return convertedQuery;
  }

  /**
   * Get search path for a connection
   */
  public getSearchPath(schemaType: 'postgres' | 'timescale' = 'postgres'): string {
    switch (schemaType) {
      case 'postgres':
        return `${this.postgresSchema}, ${this.gisSchema}, public`;
      case 'timescale':
        return `${this.timescaleSchema}, public`;
      default:
        return 'public';
    }
  }
}

// Export singleton instance
export const schemaHelper = new SchemaHelper();