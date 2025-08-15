"""Initial water accounting tables

Revision ID: 001
Revises: 
Create Date: 2025-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sections table
    op.create_table('sections',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('zone_id', sa.String(), nullable=False),
        sa.Column('area_hectares', sa.Float(), nullable=False),
        sa.Column('primary_gate_id', sa.String(), nullable=False),
        sa.Column('secondary_gate_ids', sa.JSON(), nullable=True),
        sa.Column('canal_length_km', sa.Float(), nullable=False),
        sa.Column('canal_type', sa.String(), nullable=True),
        sa.Column('seepage_coefficient', sa.Float(), nullable=False),
        sa.Column('primary_crop', sa.String(), nullable=True),
        sa.Column('crop_stage', sa.String(), nullable=True),
        sa.Column('planting_date', sa.DateTime(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create section_metrics table
    op.create_table('section_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('section_id', sa.String(), nullable=False),
        sa.Column('total_delivered_m3', sa.Float(), nullable=True),
        sa.Column('total_losses_m3', sa.Float(), nullable=True),
        sa.Column('total_applied_m3', sa.Float(), nullable=True),
        sa.Column('total_return_flow_m3', sa.Float(), nullable=True),
        sa.Column('delivery_efficiency', sa.Float(), nullable=True),
        sa.Column('application_efficiency', sa.Float(), nullable=True),
        sa.Column('overall_efficiency', sa.Float(), nullable=True),
        sa.Column('current_deficit_m3', sa.Float(), nullable=True),
        sa.Column('accumulated_deficit_m3', sa.Float(), nullable=True),
        sa.Column('deficit_weeks', sa.Integer(), nullable=True),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('last_updated', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['section_id'], ['sections.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create water_deliveries table
    op.create_table('water_deliveries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('delivery_id', sa.String(), nullable=False),
        sa.Column('section_id', sa.String(), nullable=False),
        sa.Column('scheduled_start', sa.DateTime(), nullable=False),
        sa.Column('scheduled_end', sa.DateTime(), nullable=False),
        sa.Column('scheduled_volume_m3', sa.Float(), nullable=False),
        sa.Column('actual_start', sa.DateTime(), nullable=True),
        sa.Column('actual_end', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'PARTIAL', 'FAILED', name='deliverystatus'), nullable=True),
        sa.Column('gate_outflow_m3', sa.Float(), nullable=True),
        sa.Column('section_inflow_m3', sa.Float(), nullable=True),
        sa.Column('transit_loss_m3', sa.Float(), nullable=True),
        sa.Column('flow_readings', sa.JSON(), nullable=True),
        sa.Column('integration_method', sa.String(), nullable=True),
        sa.Column('delivery_gates', sa.JSON(), nullable=True),
        sa.Column('canal_segments', sa.JSON(), nullable=True),
        sa.Column('travel_time_minutes', sa.Float(), nullable=True),
        sa.Column('weather_conditions', sa.JSON(), nullable=True),
        sa.Column('canal_condition', sa.String(), nullable=True),
        sa.Column('operator_id', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['section_id'], ['sections.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('delivery_id')
    )
    
    # Create transit_losses table
    op.create_table('transit_losses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('delivery_id', sa.Integer(), nullable=False),
        sa.Column('loss_type', sa.Enum('SEEPAGE', 'EVAPORATION', 'OPERATIONAL', 'STRUCTURAL', 'UNKNOWN', name='losstype'), nullable=False),
        sa.Column('loss_volume_m3', sa.Float(), nullable=False),
        sa.Column('loss_percentage', sa.Float(), nullable=True),
        sa.Column('canal_segment', sa.String(), nullable=True),
        sa.Column('start_chainage_km', sa.Float(), nullable=True),
        sa.Column('end_chainage_km', sa.Float(), nullable=True),
        sa.Column('flow_rate_m3s', sa.Float(), nullable=True),
        sa.Column('transit_time_hours', sa.Float(), nullable=True),
        sa.Column('wetted_perimeter_m', sa.Float(), nullable=True),
        sa.Column('water_temperature_c', sa.Float(), nullable=True),
        sa.Column('air_temperature_c', sa.Float(), nullable=True),
        sa.Column('humidity_percent', sa.Float(), nullable=True),
        sa.Column('wind_speed_ms', sa.Float(), nullable=True),
        sa.Column('solar_radiation_wm2', sa.Float(), nullable=True),
        sa.Column('soil_type', sa.String(), nullable=True),
        sa.Column('canal_condition', sa.String(), nullable=True),
        sa.Column('seepage_rate_m3_per_m2_per_day', sa.Float(), nullable=True),
        sa.Column('calculation_method', sa.String(), nullable=True),
        sa.Column('calculation_parameters', sa.JSON(), nullable=True),
        sa.Column('confidence_level', sa.Float(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['delivery_id'], ['water_deliveries.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create efficiency_records table
    op.create_table('efficiency_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('section_id', sa.String(), nullable=False),
        sa.Column('delivery_id', sa.String(), nullable=False),
        sa.Column('delivered_volume_m3', sa.Float(), nullable=False),
        sa.Column('applied_volume_m3', sa.Float(), nullable=False),
        sa.Column('consumed_volume_m3', sa.Float(), nullable=False),
        sa.Column('return_flow_m3', sa.Float(), nullable=True),
        sa.Column('conveyance_efficiency', sa.Float(), nullable=True),
        sa.Column('application_efficiency', sa.Float(), nullable=True),
        sa.Column('overall_efficiency', sa.Float(), nullable=True),
        sa.Column('seepage_loss_m3', sa.Float(), nullable=True),
        sa.Column('evaporation_loss_m3', sa.Float(), nullable=True),
        sa.Column('operational_loss_m3', sa.Float(), nullable=True),
        sa.Column('uniformity_coefficient', sa.Float(), nullable=True),
        sa.Column('adequacy_indicator', sa.Float(), nullable=True),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('calculation_method', sa.String(), nullable=True),
        sa.Column('data_quality_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['section_id'], ['sections.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create efficiency_reports table
    op.create_table('efficiency_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('report_id', sa.String(), nullable=False),
        sa.Column('report_type', sa.String(), nullable=True),
        sa.Column('zone_id', sa.String(), nullable=True),
        sa.Column('section_ids', sa.JSON(), nullable=True),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('total_sections', sa.Integer(), nullable=True),
        sa.Column('total_deliveries', sa.Integer(), nullable=True),
        sa.Column('total_volume_delivered_m3', sa.Float(), nullable=True),
        sa.Column('total_volume_consumed_m3', sa.Float(), nullable=True),
        sa.Column('avg_conveyance_efficiency', sa.Float(), nullable=True),
        sa.Column('avg_application_efficiency', sa.Float(), nullable=True),
        sa.Column('avg_overall_efficiency', sa.Float(), nullable=True),
        sa.Column('sections_above_target', sa.Integer(), nullable=True),
        sa.Column('sections_below_target', sa.Integer(), nullable=True),
        sa.Column('efficiency_distribution', sa.JSON(), nullable=True),
        sa.Column('best_performing_sections', sa.JSON(), nullable=True),
        sa.Column('worst_performing_sections', sa.JSON(), nullable=True),
        sa.Column('improvement_recommendations', sa.JSON(), nullable=True),
        sa.Column('generated_by', sa.String(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('report_data', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('report_id')
    )
    
    # Create deficit_records table
    op.create_table('deficit_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('section_id', sa.String(), nullable=False),
        sa.Column('week_number', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('water_demand_m3', sa.Float(), nullable=False),
        sa.Column('water_delivered_m3', sa.Float(), nullable=False),
        sa.Column('water_consumed_m3', sa.Float(), nullable=False),
        sa.Column('delivery_deficit_m3', sa.Float(), nullable=True),
        sa.Column('consumption_deficit_m3', sa.Float(), nullable=True),
        sa.Column('deficit_percentage', sa.Float(), nullable=True),
        sa.Column('previous_deficit_m3', sa.Float(), nullable=True),
        sa.Column('accumulated_deficit_m3', sa.Float(), nullable=True),
        sa.Column('deficit_age_weeks', sa.Integer(), nullable=True),
        sa.Column('estimated_yield_impact', sa.Float(), nullable=True),
        sa.Column('stress_level', sa.String(), nullable=True),
        sa.Column('recovery_priority', sa.Integer(), nullable=True),
        sa.Column('compensation_scheduled', sa.Boolean(), nullable=True),
        sa.Column('compensation_volume_m3', sa.Float(), nullable=True),
        sa.Column('compensation_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['section_id'], ['sections.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create deficit_carryforward table
    op.create_table('deficit_carryforward',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('section_id', sa.String(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.Column('total_deficit_m3', sa.Float(), nullable=False),
        sa.Column('oldest_deficit_week', sa.Integer(), nullable=True),
        sa.Column('newest_deficit_week', sa.Integer(), nullable=True),
        sa.Column('deficit_breakdown', sa.JSON(), nullable=True),
        sa.Column('weeks_in_deficit', sa.Integer(), nullable=True),
        sa.Column('recovery_plan', sa.JSON(), nullable=True),
        sa.Column('recovery_status', sa.String(), nullable=True),
        sa.Column('recovery_start_date', sa.DateTime(), nullable=True),
        sa.Column('recovery_target_date', sa.DateTime(), nullable=True),
        sa.Column('priority_score', sa.Float(), nullable=True),
        sa.Column('cumulative_stress_index', sa.Float(), nullable=True),
        sa.Column('compensation_history', sa.JSON(), nullable=True),
        sa.Column('last_full_delivery', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['section_id'], ['sections.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create reconciliation_logs table
    op.create_table('reconciliation_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('reconciliation_id', sa.String(), nullable=False),
        sa.Column('week_number', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('zone_id', sa.String(), nullable=True),
        sa.Column('section_ids', sa.JSON(), nullable=True),
        sa.Column('auto_data_count', sa.Integer(), nullable=True),
        sa.Column('manual_data_count', sa.Integer(), nullable=True),
        sa.Column('missing_data_count', sa.Integer(), nullable=True),
        sa.Column('total_gate_outflow_m3', sa.Float(), nullable=True),
        sa.Column('total_section_inflow_m3', sa.Float(), nullable=True),
        sa.Column('total_losses_m3', sa.Float(), nullable=True),
        sa.Column('unaccounted_volume_m3', sa.Float(), nullable=True),
        sa.Column('manual_corrections', sa.JSON(), nullable=True),
        sa.Column('adjustment_volume_m3', sa.Float(), nullable=True),
        sa.Column('adjustment_reason', sa.String(), nullable=True),
        sa.Column('data_quality_score', sa.Float(), nullable=True),
        sa.Column('confidence_level', sa.Float(), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'IN_PROGRESS', 'COMPLETED', 'APPROVED', 'DISPUTED', name='reconciliationstatus'), nullable=True),
        sa.Column('reconciled_by', sa.String(), nullable=True),
        sa.Column('approved_by', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('reconciliation_data', sa.JSON(), nullable=True),
        sa.Column('discrepancy_analysis', sa.JSON(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('issues_found', sa.JSON(), nullable=True),
        sa.Column('actions_required', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reconciliation_id')
    )
    
    # Create reconciliation_details table
    op.create_table('reconciliation_details',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('reconciliation_id', sa.String(), nullable=False),
        sa.Column('section_id', sa.String(), nullable=False),
        sa.Column('delivery_id', sa.String(), nullable=True),
        sa.Column('original_gate_outflow_m3', sa.Float(), nullable=True),
        sa.Column('original_section_inflow_m3', sa.Float(), nullable=True),
        sa.Column('original_loss_m3', sa.Float(), nullable=True),
        sa.Column('reconciled_gate_outflow_m3', sa.Float(), nullable=True),
        sa.Column('reconciled_section_inflow_m3', sa.Float(), nullable=True),
        sa.Column('reconciled_loss_m3', sa.Float(), nullable=True),
        sa.Column('adjustment_type', sa.String(), nullable=True),
        sa.Column('adjustment_value_m3', sa.Float(), nullable=True),
        sa.Column('adjustment_confidence', sa.Float(), nullable=True),
        sa.Column('data_source', sa.String(), nullable=True),
        sa.Column('data_quality', sa.String(), nullable=True),
        sa.Column('validated', sa.Boolean(), nullable=True),
        sa.Column('validation_method', sa.String(), nullable=True),
        sa.Column('validation_notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['reconciliation_id'], ['reconciliation_logs.reconciliation_id'], ),
        sa.ForeignKeyConstraint(['section_id'], ['sections.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_deliveries_section_time', 'water_deliveries', ['section_id', 'scheduled_start'])
    op.create_index('idx_deficit_section_week', 'deficit_records', ['section_id', 'week_number', 'year'])
    op.create_index('idx_efficiency_section_time', 'efficiency_records', ['section_id', 'period_start'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_efficiency_section_time', table_name='efficiency_records')
    op.drop_index('idx_deficit_section_week', table_name='deficit_records')
    op.drop_index('idx_deliveries_section_time', table_name='water_deliveries')
    
    # Drop tables in reverse order
    op.drop_table('reconciliation_details')
    op.drop_table('reconciliation_logs')
    op.drop_table('deficit_carryforward')
    op.drop_table('deficit_records')
    op.drop_table('efficiency_reports')
    op.drop_table('efficiency_records')
    op.drop_table('transit_losses')
    op.drop_table('water_deliveries')
    op.drop_table('section_metrics')
    op.drop_table('sections')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS reconciliationstatus')
    op.execute('DROP TYPE IF EXISTS deliverystatus')
    op.execute('DROP TYPE IF EXISTS losstype')