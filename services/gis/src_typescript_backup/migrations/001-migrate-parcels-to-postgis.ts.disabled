import { MigrationInterface, QueryRunner } from 'typeorm';

export class MigrateParcelsToPostGIS1234567890123 implements MigrationInterface {
  name = 'MigrateParcelsToPostGIS1234567890123';

  public async up(queryRunner: QueryRunner): Promise<void> {
    const schema = process.env.GIS_DATABASE_SCHEMA || 'gis';
    
    // Check if PostGIS is available
    const postgisCheck = await queryRunner.query(`
      SELECT EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'postgis'
      ) as postgis_exists
    `);
    
    if (!postgisCheck[0].postgis_exists) {
      console.log('PostGIS not installed, skipping migration');
      return;
    }

    console.log('Starting parcel migration to PostGIS...');

    // Create the parcels table with PostGIS geometry types if it doesn't exist
    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS ${schema}.parcels (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        parcel_code VARCHAR NOT NULL UNIQUE,
        land_title_no VARCHAR,
        geometry geometry(Polygon, 4326) NOT NULL,
        centroid geometry(Point, 4326) NOT NULL,
        area FLOAT NOT NULL,
        perimeter FLOAT NOT NULL,
        elevation_min FLOAT,
        elevation_max FLOAT,
        elevation_avg FLOAT,
        slope FLOAT,
        status VARCHAR DEFAULT 'active',
        land_use_type VARCHAR DEFAULT 'rice',
        irrigation_method VARCHAR DEFAULT 'flooding',
        owner_id VARCHAR,
        owner_name VARCHAR,
        owner_contact VARCHAR,
        zone_id VARCHAR NOT NULL,
        irrigation_block_id VARCHAR,
        canal_distance FLOAT,
        water_source_distance FLOAT,
        has_water_access BOOLEAN DEFAULT true,
        water_allocation FLOAT,
        soil_type VARCHAR,
        crop_rotation JSONB,
        properties JSONB,
        last_survey_date TIMESTAMP,
        is_smart_farm BOOLEAN DEFAULT false,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Create indexes on the parcels table
    await queryRunner.query(`CREATE INDEX IF NOT EXISTS idx_parcels_geometry ON ${schema}.parcels USING GIST (geometry)`);
    await queryRunner.query(`CREATE INDEX IF NOT EXISTS idx_parcels_centroid ON ${schema}.parcels USING GIST (centroid)`);
    await queryRunner.query(`CREATE INDEX IF NOT EXISTS idx_parcels_parcel_code ON ${schema}.parcels (parcel_code)`);
    await queryRunner.query(`CREATE INDEX IF NOT EXISTS idx_parcels_owner_id ON ${schema}.parcels (owner_id)`);
    await queryRunner.query(`CREATE INDEX IF NOT EXISTS idx_parcels_zone_id ON ${schema}.parcels (zone_id)`);

    // Check if parcels_simple table has data to migrate
    const simpleParcelCount = await queryRunner.query(`
      SELECT COUNT(*) as count FROM ${schema}.parcels_simple
    `);

    if (simpleParcelCount[0].count > 0) {
      console.log(`Migrating ${simpleParcelCount[0].count} parcels from parcels_simple to parcels...`);

      // Migrate data from parcels_simple to parcels
      await queryRunner.query(`
        INSERT INTO ${schema}.parcels (
          id,
          parcel_code,
          geometry,
          centroid,
          area,
          perimeter,
          status,
          land_use_type,
          owner_id,
          owner_name,
          zone_id,
          properties,
          created_at,
          updated_at
        )
        SELECT 
          id,
          parcel_code,
          ST_GeomFromGeoJSON(geometry::text),
          COALESCE(
            ST_GeomFromGeoJSON(centroid::text),
            ST_Centroid(ST_GeomFromGeoJSON(geometry::text))
          ),
          area,
          COALESCE(perimeter, ST_Perimeter(ST_GeomFromGeoJSON(geometry::text)::geography)),
          status,
          land_use_type,
          owner_id,
          owner_name,
          zone_id,
          JSONB_BUILD_OBJECT(
            'uploadId', upload_id,
            'cropType', crop_type,
            'attributes', attributes,
            'originalProperties', properties
          ),
          created_at,
          updated_at
        FROM ${schema}.parcels_simple
        ON CONFLICT (parcel_code) DO UPDATE SET
          geometry = EXCLUDED.geometry,
          centroid = EXCLUDED.centroid,
          area = EXCLUDED.area,
          perimeter = EXCLUDED.perimeter,
          status = EXCLUDED.status,
          land_use_type = EXCLUDED.land_use_type,
          owner_id = EXCLUDED.owner_id,
          owner_name = EXCLUDED.owner_name,
          zone_id = EXCLUDED.zone_id,
          properties = EXCLUDED.properties,
          updated_at = CURRENT_TIMESTAMP
      `);

      console.log('Migration completed successfully');
    } else {
      console.log('No data to migrate from parcels_simple');
    }

    // Create a view that provides backward compatibility
    await queryRunner.query(`
      CREATE OR REPLACE VIEW ${schema}.v_parcels_simple AS
      SELECT 
        id,
        parcel_code,
        properties->>'uploadId' as upload_id,
        zone_id,
        ST_AsGeoJSON(geometry)::jsonb as geometry,
        ST_AsGeoJSON(centroid)::jsonb as centroid,
        area,
        perimeter,
        status,
        land_use_type,
        owner_id,
        owner_name,
        properties->>'cropType' as crop_type,
        properties->'attributes' as attributes,
        properties as properties,
        created_at,
        updated_at
      FROM ${schema}.parcels
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    const schema = process.env.GIS_DATABASE_SCHEMA || 'gis';
    
    // Drop the view
    await queryRunner.query(`DROP VIEW IF EXISTS ${schema}.v_parcels_simple`);
    
    // Note: We don't drop the parcels table or migrate data back
    // as this could cause data loss in production
    console.log('Rollback completed - parcels table retained');
  }
}