-- Canonical immutable D..D+6 water-requirement publication lineage.
-- Apply: python migrations/migrate.py apply 0002_water_requirement_publication

CREATE SCHEMA IF NOT EXISTS ros_gis;

CREATE TABLE ros_gis.water_requirement_runs (
    run_id UUID PRIMARY KEY,
    as_of_date DATE NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Asia/Bangkok'
        CHECK (timezone = 'Asia/Bangkok'),
    horizon_start DATE NOT NULL,
    horizon_end DATE NOT NULL,
    input_cutoff_at TIMESTAMPTZ NOT NULL,
    section_dataset_version_id INTEGER NOT NULL,
    section_dataset_kind VARCHAR(30) NOT NULL DEFAULT 'section_master'
        CHECK (section_dataset_kind = 'section_master'),
    gate_mapping_dataset_version_id INTEGER NOT NULL,
    gate_mapping_dataset_kind VARCHAR(30) NOT NULL DEFAULT 'gate_crosswalk'
        CHECK (gate_mapping_dataset_kind = 'gate_crosswalk'),
    crop_register_version TEXT NOT NULL CHECK (btrim(crop_register_version) <> ''),
    weather_version TEXT NOT NULL CHECK (btrim(weather_version) <> ''),
    method_version TEXT NOT NULL CHECK (btrim(method_version) <> ''),
    content_hash TEXT NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    status TEXT NOT NULL DEFAULT 'calculating'
        CHECK (status IN ('calculating', 'published', 'failed', 'superseded')),
    computed_at TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ,
    failure_reason TEXT,
    FOREIGN KEY (section_dataset_version_id, section_dataset_kind)
        REFERENCES ros_gis.dataset_versions (dataset_version_id, dataset_kind),
    FOREIGN KEY (gate_mapping_dataset_version_id, gate_mapping_dataset_kind)
        REFERENCES ros_gis.dataset_versions (dataset_version_id, dataset_kind),
    CHECK (horizon_start = as_of_date),
    CHECK (horizon_start <= horizon_end),
    CHECK (input_cutoff_at <= computed_at),
    CHECK (published_at IS NULL OR published_at >= computed_at),
    CHECK (
        (published_at IS NOT NULL)
        = (status IN ('published', 'superseded'))
    ),
    CHECK (
        (failure_reason IS NOT NULL AND btrim(failure_reason) <> '')
        = (status = 'failed')
    )
);

CREATE UNIQUE INDEX uq_water_requirement_runs_one_published_day
    ON ros_gis.water_requirement_runs (as_of_date)
    WHERE status = 'published';

CREATE TABLE ros_gis.daily_water_requirements (
    requirement_id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ros_gis.water_requirement_runs (run_id),
    service_date DATE NOT NULL,
    zone INTEGER NOT NULL CHECK (zone BETWEEN 1 AND 6),
    section_id TEXT NOT NULL CHECK (btrim(section_id) <> ''),
    required_net_volume_m3 NUMERIC(18, 6) NOT NULL,
    required_gross_volume_m3 NUMERIC(18, 6) NOT NULL,
    delivery_window_start TIMESTAMPTZ NOT NULL,
    delivery_window_end TIMESTAMPTZ NOT NULL,
    quality TEXT NOT NULL CHECK (quality IN ('estimated', 'forecast')),
    input_versions JSONB NOT NULL,
    content_hash TEXT NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, service_date, section_id),
    CHECK (
        required_net_volume_m3 >= 0
        AND required_net_volume_m3::text NOT IN ('NaN', 'Infinity', '-Infinity')
    ),
    CHECK (
        required_gross_volume_m3 >= required_net_volume_m3
        AND required_gross_volume_m3::text NOT IN ('NaN', 'Infinity', '-Infinity')
    ),
    CHECK (delivery_window_start < delivery_window_end),
    CHECK (jsonb_typeof(input_versions) = 'object')
);

CREATE TABLE ros_gis.water_requirement_contributions (
    requirement_id UUID NOT NULL
        REFERENCES ros_gis.daily_water_requirements (requirement_id),
    area_id TEXT NOT NULL CHECK (btrim(area_id) <> ''),
    area_rai NUMERIC(18, 6) NOT NULL,
    crop_type TEXT NOT NULL CHECK (btrim(crop_type) <> ''),
    crop_stage TEXT NOT NULL CHECK (btrim(crop_stage) <> ''),
    net_volume_m3 NUMERIC(18, 6) NOT NULL,
    source_payload_hash TEXT NOT NULL
        CHECK (source_payload_hash ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (requirement_id, area_id),
    CHECK (
        area_rai > 0
        AND area_rai::text NOT IN ('NaN', 'Infinity', '-Infinity')
    ),
    CHECK (
        net_volume_m3 >= 0
        AND net_volume_m3::text NOT IN ('NaN', 'Infinity', '-Infinity')
    )
);

CREATE FUNCTION ros_gis.enforce_water_requirement_run_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'water requirement runs are append-only';
    END IF;

    IF ROW(
        NEW.run_id,
        NEW.as_of_date,
        NEW.timezone,
        NEW.horizon_start,
        NEW.horizon_end,
        NEW.input_cutoff_at,
        NEW.section_dataset_version_id,
        NEW.section_dataset_kind,
        NEW.gate_mapping_dataset_version_id,
        NEW.gate_mapping_dataset_kind,
        NEW.crop_register_version,
        NEW.weather_version,
        NEW.method_version,
        NEW.content_hash,
        NEW.computed_at
    ) IS DISTINCT FROM ROW(
        OLD.run_id,
        OLD.as_of_date,
        OLD.timezone,
        OLD.horizon_start,
        OLD.horizon_end,
        OLD.input_cutoff_at,
        OLD.section_dataset_version_id,
        OLD.section_dataset_kind,
        OLD.gate_mapping_dataset_version_id,
        OLD.gate_mapping_dataset_kind,
        OLD.crop_register_version,
        OLD.weather_version,
        OLD.method_version,
        OLD.content_hash,
        OLD.computed_at
    ) THEN
        RAISE EXCEPTION 'water requirement run identity and lineage are immutable';
    END IF;

    IF OLD.status = 'calculating' AND NEW.status = 'published' THEN
        IF NOT EXISTS (
            SELECT 1
            FROM ros_gis.daily_water_requirements
            WHERE run_id = NEW.run_id
        ) THEN
            RAISE EXCEPTION 'publication needs at least one requirement';
        END IF;
        IF EXISTS (
            SELECT 1
            FROM ros_gis.daily_water_requirements AS requirement
            JOIN ros_gis.water_requirement_contributions AS contribution
                USING (requirement_id)
            WHERE requirement.run_id = NEW.run_id
            GROUP BY requirement.requirement_id, requirement.required_net_volume_m3
            HAVING SUM(contribution.net_volume_m3) <> requirement.required_net_volume_m3
        ) THEN
            RAISE EXCEPTION 'contribution net volume does not match requirement net volume';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status = 'calculating' AND NEW.status = 'failed' THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'published' AND NEW.status = 'superseded' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'invalid water requirement run transition: % -> %',
        OLD.status, NEW.status;
END
$$;

CREATE TRIGGER water_requirement_runs_are_append_only
    BEFORE UPDATE OR DELETE ON ros_gis.water_requirement_runs
    FOR EACH ROW EXECUTE FUNCTION ros_gis.enforce_water_requirement_run_transition();

CREATE FUNCTION ros_gis.validate_daily_requirement_run()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    run ros_gis.water_requirement_runs%ROWTYPE;
BEGIN
    SELECT * INTO run
    FROM ros_gis.water_requirement_runs
    WHERE run_id = NEW.run_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'water requirement run % does not exist', NEW.run_id;
    END IF;
    IF run.status <> 'calculating' THEN
        RAISE EXCEPTION 'requirements may only be added to a calculating run';
    END IF;
    IF NEW.service_date < run.horizon_start
       OR NEW.service_date > run.horizon_end THEN
        RAISE EXCEPTION 'requirement service date lies outside its run horizon';
    END IF;
    IF NEW.service_date = run.as_of_date AND NEW.quality <> 'estimated' THEN
        RAISE EXCEPTION 'the as-of-date requirement quality must be estimated';
    END IF;
    IF NEW.service_date > run.as_of_date AND NEW.quality <> 'forecast' THEN
        RAISE EXCEPTION 'future requirement quality must be forecast';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER daily_water_requirement_run_is_valid
    BEFORE INSERT ON ros_gis.daily_water_requirements
    FOR EACH ROW EXECUTE FUNCTION ros_gis.validate_daily_requirement_run();

CREATE FUNCTION ros_gis.validate_water_requirement_contribution_run()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    run_status TEXT;
BEGIN
    SELECT run.status INTO run_status
    FROM ros_gis.daily_water_requirements AS requirement
    JOIN ros_gis.water_requirement_runs AS run USING (run_id)
    WHERE requirement.requirement_id = NEW.requirement_id
    FOR SHARE OF run;

    IF run_status IS NULL THEN
        RAISE EXCEPTION 'contribution requirement % does not exist', NEW.requirement_id;
    END IF;
    IF run_status <> 'calculating' THEN
        RAISE EXCEPTION 'contributions may only be added to a calculating run';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER water_requirement_contribution_run_is_valid
    BEFORE INSERT ON ros_gis.water_requirement_contributions
    FOR EACH ROW EXECUTE FUNCTION ros_gis.validate_water_requirement_contribution_run();

CREATE FUNCTION ros_gis.reject_water_requirement_item_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'published water requirement rows are immutable';
END
$$;

CREATE TRIGGER daily_water_requirements_are_immutable
    BEFORE UPDATE OR DELETE ON ros_gis.daily_water_requirements
    FOR EACH ROW EXECUTE FUNCTION ros_gis.reject_water_requirement_item_change();

CREATE TRIGGER water_requirement_contributions_are_immutable
    BEFORE UPDATE OR DELETE ON ros_gis.water_requirement_contributions
    FOR EACH ROW EXECUTE FUNCTION ros_gis.reject_water_requirement_item_change();
