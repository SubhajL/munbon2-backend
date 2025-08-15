                                          ?column?                                           
---------------------------------------------------------------------------------------------
 CREATE TABLE ros.area_info (                                                               +
     id integer NOT NULL DEFAULT nextval('ros.area_info_id_seq'::regclass),                 +
     area_id VARCHAR(50) NOT NULL,                                                          +
     area_type VARCHAR(20) NOT NULL,                                                        +
     area_name VARCHAR(200),                                                                +
     total_area_rai DECIMAL(10,2),                                                          +
     parent_area_id VARCHAR(50),                                                            +
     aos_station VARCHAR(100) DEFAULT 'นครราชสีมา'::character varying,                       +
     province VARCHAR(100) DEFAULT 'นครราชสีมา'::character varying,                          +
     created_at TIMESTAMP DEFAULT now(),                                                    +
     updated_at TIMESTAMP DEFAULT now()                                                     +
 );
 CREATE TABLE ros.crop_calendar (                                                           +
     id integer NOT NULL DEFAULT nextval('ros.crop_calendar_id_seq'::regclass),             +
     area_id VARCHAR(50) NOT NULL,                                                          +
     area_type VARCHAR(20) NOT NULL,                                                        +
     crop_type VARCHAR(50) NOT NULL,                                                        +
     planting_date date NOT NULL,                                                           +
     expected_harvest_date date,                                                            +
     season VARCHAR(20),                                                                    +
     year integer NOT NULL,                                                                 +
     total_crop_weeks integer,                                                              +
     created_at TIMESTAMP DEFAULT now(),                                                    +
     updated_at TIMESTAMP DEFAULT now()                                                     +
 );
 CREATE TABLE ros.effective_rainfall_monthly (                                              +
     id integer NOT NULL DEFAULT nextval('ros.effective_rainfall_monthly_id_seq'::regclass),+
     aos_station VARCHAR(100) NOT NULL DEFAULT 'นครราชสีมา'::character varying,              +
     province VARCHAR(100) NOT NULL DEFAULT 'นครราชสีมา'::character varying,                 +
     month integer NOT NULL,                                                                +
     crop_type VARCHAR(50) NOT NULL,                                                        +
     effective_rainfall_mm DECIMAL(10,2) NOT NULL,                                          +
     created_at TIMESTAMP DEFAULT now(),                                                    +
     updated_at TIMESTAMP DEFAULT now()                                                     +
 );
 CREATE TABLE ros.eto_monthly (                                                             +
     id integer NOT NULL DEFAULT nextval('ros.eto_monthly_id_seq'::regclass),               +
     aos_station VARCHAR(100) NOT NULL,                                                     +
     province VARCHAR(100) NOT NULL,                                                        +
     month integer NOT NULL,                                                                +
     eto_value DECIMAL(10,2) NOT NULL,                                                      +
     created_at TIMESTAMP DEFAULT now(),                                                    +
     updated_at TIMESTAMP DEFAULT now()                                                     +
 );
 CREATE TABLE ros.eto_weekly (                                                              +
     id integer NOT NULL DEFAULT nextval('ros.eto_weekly_id_seq'::regclass),                +
     aos_station VARCHAR(100) NOT NULL DEFAULT 'นครราชสีมา'::character varying,              +
     province VARCHAR(100) NOT NULL DEFAULT 'นครราชสีมา'::character varying,                 +
     calendar_week integer NOT NULL,                                                        +
     calendar_year integer NOT NULL,                                                        +
     month integer NOT NULL,                                                                +
     eto_value DECIMAL(10,2) NOT NULL,                                                      +
     created_at TIMESTAMP DEFAULT now(),                                                    +
     updated_at TIMESTAMP DEFAULT now()                                                     +
 );
 CREATE TABLE ros.kc_weekly (                                                               +
     id integer NOT NULL DEFAULT nextval('ros.kc_weekly_id_seq'::regclass),                 +
     crop_type VARCHAR(50) NOT NULL,                                                        +
     crop_week integer NOT NULL,                                                            +
     kc_value DECIMAL(4,3) NOT NULL,                                                        +
     created_at TIMESTAMP DEFAULT now(),                                                    +
     updated_at TIMESTAMP DEFAULT now()                                                     +
 );
 CREATE TABLE ros.land_preparation_water (                                                  +
     id integer NOT NULL DEFAULT nextval('ros.land_preparation_water_id_seq'::regclass),    +
     crop_type VARCHAR(50) NOT NULL,                                                        +
     preparation_water_mm DECIMAL(10,2) NOT NULL,                                           +
     preparation_weeks integer DEFAULT 1,                                                   +
     description VARCHAR(200),                                                              +
     created_at TIMESTAMP DEFAULT now(),                                                    +
     updated_at TIMESTAMP DEFAULT now()                                                     +
 );
 CREATE TABLE ros.plot_crop_schedule (                                                      +
     id integer NOT NULL DEFAULT nextval('ros.plot_crop_schedule_id_seq'::regclass),        +
     plot_id VARCHAR(50) NOT NULL,                                                          +
     crop_type VARCHAR(50) NOT NULL,                                                        +
     planting_date date NOT NULL,                                                           +
     expected_harvest_date date,                                                            +
     season VARCHAR(20) NOT NULL,                                                           +
     year integer NOT NULL,                                                                 +
     status VARCHAR(20) DEFAULT 'planned'::character varying,                               +
     created_at TIMESTAMP DEFAULT now(),                                                    +
     updated_at TIMESTAMP DEFAULT now()                                                     +
 );
 CREATE TABLE ros.plot_water_demand_seasonal (                                              +
     id integer NOT NULL DEFAULT nextval('ros.plot_water_demand_seasonal_id_seq'::regclass),+
     plot_id VARCHAR(50) NOT NULL,                                                          +
     crop_type VARCHAR(50) NOT NULL,                                                        +
     planting_date date NOT NULL,                                                           +
     harvest_date date,                                                                     +
     season VARCHAR(20) NOT NULL,                                                           +
     year integer NOT NULL,                                                                 +
     area_rai DECIMAL(10,2) NOT NULL,                                                       +
     total_crop_weeks integer NOT NULL,                                                     +
     total_water_demand_mm DECIMAL(10,2),                                                   +
     total_water_demand_m3 DECIMAL(15,2),                                                   +
     land_preparation_mm DECIMAL(10,2),                                                     +
     land_preparation_m3 DECIMAL(15,2),                                                     +
     total_effective_rainfall_mm DECIMAL(10,2),                                             +
     total_net_water_demand_mm DECIMAL(10,2),                                               +
     total_net_water_demand_m3 DECIMAL(15,2),                                               +
     calculation_date date NOT NULL DEFAULT CURRENT_DATE,                                   +
     includes_land_preparation boolean DEFAULT true,                                        +
     includes_rainfall boolean DEFAULT true,                                                +
     created_at TIMESTAMP DEFAULT now(),                                                    +
     updated_at TIMESTAMP DEFAULT now()                                                     +
 );
 CREATE TABLE ros.plot_water_demand_weekly (                                                +
     id integer NOT NULL DEFAULT nextval('ros.plot_water_demand_weekly_id_seq'::regclass),  +
     plot_id VARCHAR(50) NOT NULL,                                                          +
     crop_type VARCHAR(50) NOT NULL,                                                        +
     crop_week integer NOT NULL,                                                            +
     calendar_week integer NOT NULL,                                                        +
     calendar_year integer NOT NULL,                                                        +
     calculation_date date NOT NULL,                                                        +
     area_rai DECIMAL(10,2) NOT NULL,                                                       +
     monthly_eto DECIMAL(10,2),                                                             +
     weekly_eto DECIMAL(10,2),                                                              +
     kc_value DECIMAL(4,3),                                                                 +
     percolation DECIMAL(10,2) DEFAULT 14,                                                  +
     crop_water_demand_mm DECIMAL(10,2),                                                    +
     crop_water_demand_m3 DECIMAL(15,2),                                                    +
     effective_rainfall_mm DECIMAL(10,2),                                                   +
     net_water_demand_mm DECIMAL(10,2),                                                     +
     net_water_demand_m3 DECIMAL(15,2),                                                     +
     is_land_preparation boolean DEFAULT false,                                             +
     created_at TIMESTAMP DEFAULT now(),                                                    +
     crop_water_demand_m3_per_rai DECIMAL(15,2),                                            +
     net_water_demand_m3_per_rai DECIMAL(15,2)                                              +
 );
 CREATE TABLE ros.plots (                                                                   +
     id integer NOT NULL DEFAULT nextval('ros.plots_id_seq'::regclass),                     +
     plot_id VARCHAR(50) NOT NULL,                                                          +
     plot_code VARCHAR(50),                                                                 +
     area_rai DECIMAL(10,2) NOT NULL,                                                       +
     geometry USER-DEFINED,                                                                 +
     parent_section_id VARCHAR(50),                                                         +
     parent_zone_id VARCHAR(50),                                                            +
     aos_station VARCHAR(100) DEFAULT 'นครราชสีมา'::character varying,                       +
     province VARCHAR(100) DEFAULT 'นครราชสีมา'::character varying,                          +
     created_at TIMESTAMP DEFAULT now(),                                                    +
     updated_at TIMESTAMP DEFAULT now(),                                                    +
     current_planting_date date,                                                            +
     current_crop_type VARCHAR(50),                                                         +
     current_crop_status VARCHAR(20) DEFAULT 'active'::character varying                    +
 );
 CREATE TABLE ros.plots_temp (                                                              +
     fid integer NOT NULL DEFAULT nextval('ros.plots_temp_fid_seq'::regclass),              +
     parcel_area_rai double precision,                                                      +
     geom USER-DEFINED                                                                      +
 );
 CREATE TABLE ros.rainfall_data (                                                           +
     id integer NOT NULL DEFAULT nextval('ros.rainfall_data_id_seq'::regclass),             +
     area_id VARCHAR(50) NOT NULL,                                                          +
     date date NOT NULL,                                                                    +
     rainfall_mm DECIMAL(10,2) NOT NULL,                                                    +
     effective_rainfall_mm DECIMAL(10,2),                                                   +
     source VARCHAR(20) NOT NULL,                                                           +
     created_at TIMESTAMP DEFAULT now(),                                                    +
     updated_at TIMESTAMP DEFAULT now()                                                     +
 );
 CREATE TABLE ros.v_plots_current_crop (                                                    +
     plot_id VARCHAR(50),                                                                   +
     plot_code VARCHAR(50),                                                                 +
     area_rai DECIMAL(10,2),                                                                +
     parent_zone_id VARCHAR(50),                                                            +
     parent_section_id VARCHAR(50),                                                         +
     current_planting_date date,                                                            +
     current_crop_type VARCHAR(50),                                                         +
     current_crop_status VARCHAR(20),                                                       +
     total_water_demand_m3 DECIMAL(15,2),                                                   +
     total_net_water_demand_m3 DECIMAL(15,2),                                               +
     land_preparation_m3 DECIMAL(15,2),                                                     +
     current_crop_week integer,                                                             +
     expected_harvest_date date                                                             +
 );
 CREATE TABLE ros.water_demand_calculations (                                               +
     id integer NOT NULL DEFAULT nextval('ros.water_demand_calculations_id_seq'::regclass), +
     area_id VARCHAR(50) NOT NULL,                                                          +
     area_type VARCHAR(20) NOT NULL,                                                        +
     area_rai DECIMAL(10,2) NOT NULL,                                                       +
     crop_type VARCHAR(50) NOT NULL,                                                        +
     crop_week integer NOT NULL,                                                            +
     calendar_week integer NOT NULL,                                                        +
     calendar_year integer NOT NULL,                                                        +
     calculation_date date NOT NULL,                                                        +
     monthly_eto DECIMAL(10,2),                                                             +
     weekly_eto DECIMAL(10,2),                                                              +
     kc_value DECIMAL(4,3),                                                                 +
     percolation DECIMAL(10,2) DEFAULT 14,                                                  +
     crop_water_demand_mm DECIMAL(10,2),                                                    +
     crop_water_demand_m3 DECIMAL(15,2),                                                    +
     effective_rainfall DECIMAL(10,2),                                                      +
     water_level DECIMAL(10,2),                                                             +
     net_water_demand_mm DECIMAL(10,2),                                                     +
     net_water_demand_m3 DECIMAL(15,2),                                                     +
     created_at TIMESTAMP DEFAULT now(),                                                    +
     is_land_preparation boolean DEFAULT false,                                             +
     land_preparation_mm DECIMAL(10,2),                                                     +
     land_preparation_m3 DECIMAL(15,2)                                                      +
 );
 CREATE TABLE ros.water_level_data (                                                        +
     id integer NOT NULL DEFAULT nextval('ros.water_level_data_id_seq'::regclass),          +
     area_id VARCHAR(50) NOT NULL,                                                          +
     measurement_date date NOT NULL,                                                        +
     measurement_time time without time zone,                                               +
     water_level_m DECIMAL(10,3) NOT NULL,                                                  +
     reference_level VARCHAR(50),                                                           +
     source VARCHAR(20) NOT NULL,                                                           +
     sensor_id VARCHAR(50),                                                                 +
     created_at TIMESTAMP DEFAULT now(),                                                    +
     updated_at TIMESTAMP DEFAULT now()                                                     +
 );
(16 rows)

