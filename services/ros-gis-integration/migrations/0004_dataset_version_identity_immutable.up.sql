-- #150: make ros_gis.dataset_versions an APPEND-ONLY parent with an immutable
-- IDENTITY (planning-depth provenance drift). R0 (PR #149) binds
-- (roster_dataset_version_id, roster_source_hash) onto immutable planning-depth
-- submissions, but the parent dataset_versions row was DB-mutable AND removable:
-- only the history tables carried immutability triggers from 0001. A stored
-- provenance pair could therefore drift to identify no row -- by UPDATE of the
-- identity, or by DELETE/TRUNCATE of the parent -- silently invalidating the
-- audit identity R0 guarantees.
--
-- Unlike the history tables, dataset_versions is only PARTIALLY immutable under
-- UPDATE: status (draft -> active -> superseded) and effective_from/effective_to
-- (and source_description) are set during the lifecycle and MUST stay mutable. So
-- the UPDATE path is COLUMN-SELECTIVE (reject only when an immutable column
-- changes), while DELETE and TRUNCATE are rejected outright -- the ledger is
-- append-only; retire a version via status='superseded', never by removing the
-- row. This mirrors 0001's BEFORE UPDATE OR DELETE immutability on the history
-- tables, and adds a statement-level TRUNCATE guard so the append-only claim
-- holds against a `TRUNCATE ... CASCADE` reset as well.
--
-- Immutable columns: the identity (dataset_version_id, dataset_kind, source_hash)
-- plus created_at (a creation timestamp never legitimately changes; 0001 freezes
-- it on the history tables, and a mutable one would let audit ordering be forged).
--
-- dataset_version_id is GENERATED ALWAYS AS IDENTITY: Postgres already rejects an
-- explicit-value assignment, but PERMITS a reset to DEFAULT (a fresh sequence
-- value) which would orphan the pair, so the trigger guards dataset_version_id
-- too -- it is the only guard for that path.
--
-- DDL only -- no data statements.
-- Apply:    python migrations/migrate.py apply    0004_dataset_version_identity_immutable
-- Rollback: python migrations/migrate.py rollback 0004_dataset_version_identity_immutable

CREATE FUNCTION ros_gis.reject_dataset_version_identity_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Any non-UPDATE op (DELETE row-level, TRUNCATE statement-level) removes the
    -- row entirely, orphaning any stored (dataset_version_id, source_hash)
    -- provenance pair. Handle this before touching NEW/OLD (both absent for a
    -- statement-level TRUNCATE).
    IF TG_OP <> 'UPDATE' THEN
        RAISE EXCEPTION
            'ros_gis.dataset_versions is append-only; % would orphan provenance (dataset_version_id, dataset_kind, source_hash)',
            TG_OP;
    END IF;
    -- UPDATE: lifecycle columns stay mutable; identity + created_at are immutable.
    IF NEW.dataset_version_id IS DISTINCT FROM OLD.dataset_version_id
       OR NEW.dataset_kind IS DISTINCT FROM OLD.dataset_kind
       OR NEW.source_hash IS DISTINCT FROM OLD.source_hash
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'ros_gis.dataset_versions identity is immutable (dataset_version_id, dataset_kind, source_hash, created_at)';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER dataset_versions_identity_is_immutable
    BEFORE UPDATE OR DELETE ON ros_gis.dataset_versions
    FOR EACH ROW EXECUTE FUNCTION ros_gis.reject_dataset_version_identity_change();

CREATE TRIGGER dataset_versions_no_truncate
    BEFORE TRUNCATE ON ros_gis.dataset_versions
    FOR EACH STATEMENT EXECUTE FUNCTION ros_gis.reject_dataset_version_identity_change();
