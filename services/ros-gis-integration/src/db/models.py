"""
Database models for ROS/GIS Integration Service
Using SQLAlchemy with asyncpg
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
    Index,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
    CheckConstraint,
    DECIMAL,
    Identity,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry

Base = declarative_base()
VersionedBase = declarative_base()

# The single gate-id grammar (flow-monitoring core/node_id.py M(i,j) vocabulary,
# compact or survey-spaced). Cross-pinned by test against the migration SQL CHECK —
# Postgres POSIX `~` and Python `re` read this pattern identically.
GATE_ID_PATTERN = r"^M ?\(\d+,\d+(; ?\d+,\d+)*\)$"

# Validity interval as a range expression (NULL valid_to = open-ended). Used by the
# exclusion constraints that make "reject overlapping validity ranges" (HIGH #5) a
# database guarantee instead of an application-side promise.
_VALIDITY_RANGE = "tstzrange(valid_from, COALESCE(valid_to, 'infinity'::timestamptz))"


class DatasetVersion(VersionedBase):
    """Wave 2.5 (HIGH #5): the version parent every section-master / crosswalk
    snapshot hangs off. Exactly one ACTIVE dataset per kind at a time; promotion
    is an atomic status flip (draft -> active, old active -> superseded)."""

    __tablename__ = "dataset_versions"

    dataset_version_id = Column(Integer, Identity(always=True), primary_key=True)
    dataset_kind = Column(String(30), nullable=False)
    source_hash = Column(
        String(64), nullable=False
    )  # content-address of the source snapshot
    source_description = Column(String(500))
    status = Column(String(15), nullable=False, server_default="draft")
    effective_from = Column(DateTime(timezone=True))
    effective_to = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("dataset_version_id", "dataset_kind"),
        CheckConstraint("dataset_kind IN ('section_master', 'gate_crosswalk')"),
        CheckConstraint("status IN ('draft', 'active', 'superseded')"),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_from < effective_to"
        ),
        Index(
            "uq_dataset_versions_one_active_per_kind",
            "dataset_kind",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        {"schema": "ros_gis"},
    )


class SectionMasterVersion(VersionedBase):
    """Immutable, effective-dated section master rows under a dataset version.
    Geometry is MULTIPOLYGON on purpose: invalid-geometry repairs may widen
    POLYGON sources (the 2.5 schema trap)."""

    __tablename__ = "section_master_history"

    dataset_version_id = Column(
        Integer,
        primary_key=True,
    )
    dataset_kind = Column(
        String(30), nullable=False, server_default=text("'section_master'")
    )
    section_id = Column(String(50), primary_key=True)
    valid_from = Column(DateTime(timezone=True), primary_key=True)
    valid_to = Column(DateTime(timezone=True))
    zone = Column(Integer, nullable=False)
    source_code = Column(String(50))  # gis.zone `code` / Plot_id vocabulary (2.5a spec)
    area_hectares = Column(DECIMAL(10, 2))
    area_rai = Column(DECIMAL(12, 2))
    irrigation_channel = Column(String(100))
    delivery_gate = Column(String(50))
    geometry = Column(Geometry("MULTIPOLYGON", srid=4326))
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("dataset_kind = 'section_master'"),
        CheckConstraint("valid_to IS NULL OR valid_from < valid_to"),
        ForeignKeyConstraint(
            ("dataset_version_id", "dataset_kind"),
            (
                "ros_gis.dataset_versions.dataset_version_id",
                "ros_gis.dataset_versions.dataset_kind",
            ),
        ),
        ExcludeConstraint(
            (text("dataset_version_id"), "="),
            (text("section_id"), "="),
            (text(_VALIDITY_RANGE), "&&"),
            using="gist",
            name="excl_section_history_overlapping_validity",
        ),
        {"schema": "ros_gis"},
    )


class GateMappingVersion(VersionedBase):
    """Immutable, effective-dated section->gate crosswalk rows under a dataset
    version. Primary-exclusivity is scoped per (dataset, section, interval) —
    historical primaries stay storable (the HIGH #5 defect)."""

    __tablename__ = "gate_mapping_history"

    dataset_version_id = Column(
        Integer,
        primary_key=True,
    )
    dataset_kind = Column(
        String(30), nullable=False, server_default=text("'gate_crosswalk'")
    )
    section_id = Column(String(50), primary_key=True)
    gate_id = Column(String(50), primary_key=True)
    valid_from = Column(DateTime(timezone=True), primary_key=True)
    valid_to = Column(DateTime(timezone=True))
    is_primary = Column(Boolean, nullable=False, server_default=text("false"))
    irrigation_channel = Column(String(100))
    distance_km = Column(DECIMAL(6, 2))
    travel_time_hours = Column(
        DECIMAL(5, 2)
    )  # metadata/cache, never the path calc (3.2)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("dataset_kind = 'gate_crosswalk'"),
        CheckConstraint("valid_to IS NULL OR valid_from < valid_to"),
        ForeignKeyConstraint(
            ("dataset_version_id", "dataset_kind"),
            (
                "ros_gis.dataset_versions.dataset_version_id",
                "ros_gis.dataset_versions.dataset_kind",
            ),
        ),
        CheckConstraint(f"gate_id ~ '{GATE_ID_PATTERN}'"),
        ExcludeConstraint(
            (text("dataset_version_id"), "="),
            (text("section_id"), "="),
            (text("gate_id"), "="),
            (text(_VALIDITY_RANGE), "&&"),
            using="gist",
            name="excl_gate_mapping_history_overlapping_validity",
        ),
        ExcludeConstraint(
            (text("dataset_version_id"), "="),
            (text("section_id"), "="),
            (text(_VALIDITY_RANGE), "&&"),
            using="gist",
            where=text("is_primary"),
            name="excl_gate_mapping_history_one_primary_per_interval",
        ),
        {"schema": "ros_gis"},
    )


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (
        CheckConstraint(
            "geometry IS NULL OR GeometryType(geometry) IN ('POLYGON', 'MULTIPOLYGON')",
            name="chk_sections_polygonal_geometry",
        ),
        {"schema": "ros_gis"},
    )

    section_id = Column(String(50), primary_key=True)
    zone = Column(Integer, nullable=False)
    area_hectares = Column(DECIMAL(10, 2))
    area_rai = Column(DECIMAL(10, 2))  # Generated column
    crop_type = Column(String(50))
    soil_type = Column(String(50))
    elevation_m = Column(DECIMAL(6, 2))
    delivery_gate = Column(String(50))
    irrigation_channel = Column(String(100))
    geometry = Column(Geometry("GEOMETRY", srid=4326))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    demands = relationship("Demand", back_populates="section")
    performances = relationship("SectionPerformance", back_populates="section")
    gate_mappings = relationship("GateMapping", back_populates="section")
    weather_adjustments = relationship("WeatherAdjustment", back_populates="section")


class Demand(Base):
    __tablename__ = "demands"
    __table_args__ = {"schema": "ros_gis"}

    demand_id = Column(Integer, primary_key=True)
    section_id = Column(String(50), ForeignKey("ros_gis.sections.section_id"))
    week = Column(String(8), nullable=False)
    volume_m3 = Column(DECIMAL(12, 2))
    priority = Column(DECIMAL(3, 1))
    priority_class = Column(String(20))
    crop_type = Column(String(50))
    growth_stage = Column(String(50))
    moisture_deficit_percent = Column(DECIMAL(5, 2))
    stress_level = Column(String(20))
    delivery_window_start = Column(DateTime)
    delivery_window_end = Column(DateTime)
    weather_adjustment_factor = Column(DECIMAL(4, 3), server_default="1.0")
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    section = relationship("Section", back_populates="demands")

    __table_args__ = (
        CheckConstraint("priority >= 0 AND priority <= 10"),
        CheckConstraint("priority_class IN ('critical', 'high', 'medium', 'low')"),
        CheckConstraint(
            "stress_level IN ('none', 'mild', 'moderate', 'severe', 'critical')"
        ),
        {"schema": "ros_gis"},
    )


class SectionPerformance(Base):
    __tablename__ = "section_performance"
    __table_args__ = {"schema": "ros_gis"}

    performance_id = Column(Integer, primary_key=True)
    section_id = Column(String(50), ForeignKey("ros_gis.sections.section_id"))
    week = Column(String(8), nullable=False)
    planned_m3 = Column(DECIMAL(12, 2))
    delivered_m3 = Column(DECIMAL(12, 2))
    efficiency = Column(DECIMAL(3, 2))
    deficit_m3 = Column(DECIMAL(12, 2))
    delivery_count = Column(Integer, default=0)
    average_flow_m3s = Column(DECIMAL(8, 3))
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    section = relationship("Section", back_populates="performances")

    __table_args__ = (
        CheckConstraint("efficiency >= 0 AND efficiency <= 1"),
        {"schema": "ros_gis"},
    )


class GateMapping(Base):
    __tablename__ = "gate_mappings"
    __table_args__ = {"schema": "ros_gis"}

    mapping_id = Column(Integer, primary_key=True)
    gate_id = Column(String(50), nullable=False)
    section_id = Column(String(50), ForeignKey("ros_gis.sections.section_id"))
    irrigation_channel = Column(String(100))
    distance_km = Column(DECIMAL(6, 2))
    travel_time_hours = Column(DECIMAL(5, 2))
    is_primary = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    section = relationship("Section", back_populates="gate_mappings")

    __table_args__ = (
        UniqueConstraint("gate_id", "section_id"),
        # One PRIMARY gate per section in the CURRENT projection (2.5 hardening;
        # history keeps per-interval exclusivity in gate_mapping_history).
        Index(
            "uq_gate_mappings_one_primary_per_section",
            "section_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
        {"schema": "ros_gis"},
    )


class GateDemand(Base):
    __tablename__ = "gate_demands"
    __table_args__ = {"schema": "ros_gis"}

    gate_demand_id = Column(Integer, primary_key=True)
    gate_id = Column(String(50), nullable=False)
    week = Column(String(8), nullable=False)
    total_volume_m3 = Column(DECIMAL(12, 2))
    section_count = Column(Integer)
    priority_weighted = Column(DECIMAL(3, 1))
    schedule_id = Column(String(100))
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("gate_id", "week"), {"schema": "ros_gis"})


class WeatherAdjustment(Base):
    __tablename__ = "weather_adjustments"
    __table_args__ = {"schema": "ros_gis"}

    adjustment_id = Column(Integer, primary_key=True)
    section_id = Column(String(50), ForeignKey("ros_gis.sections.section_id"))
    week = Column(String(8), nullable=False)
    rainfall_mm = Column(DECIMAL(6, 2))
    et_mm = Column(DECIMAL(6, 2))
    adjustment_factor = Column(DECIMAL(4, 3))
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    section = relationship("Section", back_populates="weather_adjustments")
