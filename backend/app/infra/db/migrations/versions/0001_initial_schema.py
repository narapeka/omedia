from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watch_settings",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "depots",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("target_library_path", sa.Text(), nullable=False),
        sa.Column("transfer_trigger", sa.Text(), nullable=False),
        sa.Column("transfer_rule_id", sa.Text(), nullable=True),
        sa.Column("schedule", sa.Text(), nullable=True),
        sa.Column("resolve_mode", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_depots_name", "depots", ["name"])
    op.create_index("idx_depots_path", "depots", ["path"], unique=True)

    op.create_table(
        "origins",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("target_depot_id", sa.Text(), nullable=False),
        sa.Column("organize_rule_id", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_origins_name", "origins", ["name"])
    op.create_index("idx_origins_path", "origins", ["path"], unique=True)
    op.create_index("idx_origins_trigger", "origins", ["trigger"])

    op.create_table(
        "organize_rules",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("categories_json", sa.Text(), nullable=False),
        sa.Column("fallback_bucket", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_organize_rules_name", "organize_rules", ["name"])

    op.create_table(
        "transfer_rules",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("categories_json", sa.Text(), nullable=False),
        sa.Column("fallback_bucket", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_transfer_rules_name", "transfer_rules", ["name"])

    op.create_table(
        "tmdb_detail_cache",
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("media_type", "tmdb_id"),
    )

    op.create_table(
        "activity_events",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("time", sa.Text(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.Column("entity_source", sa.Text(), nullable=True),
        sa.Column("entity_target", sa.Text(), nullable=True),
        sa.Column("media_type", sa.Text(), nullable=True),
        sa.Column("tmdb_id", sa.Text(), nullable=True),
        sa.Column("origin_id", sa.Text(), nullable=True),
        sa.Column("origin_name", sa.Text(), nullable=True),
        sa.Column("origin_path", sa.Text(), nullable=True),
        sa.Column("depot_id", sa.Text(), nullable=True),
        sa.Column("depot_name", sa.Text(), nullable=True),
        sa.Column("depot_path", sa.Text(), nullable=True),
        sa.Column("library_path", sa.Text(), nullable=True),
        sa.Column("rule_id", sa.Text(), nullable=True),
        sa.Column("rule_name", sa.Text(), nullable=True),
        sa.Column("context_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_activity_events_action", "activity_events", ["action"])
    op.create_index("idx_activity_events_area", "activity_events", ["area"])
    op.create_index("idx_activity_events_depot_id", "activity_events", ["depot_id"])
    op.create_index("idx_activity_events_entity_source", "activity_events", ["entity_source"])
    op.create_index("idx_activity_events_entity_target", "activity_events", ["entity_target"])
    op.create_index("idx_activity_events_entity_type", "activity_events", ["entity_type"])
    op.create_index("idx_activity_events_library_path", "activity_events", ["library_path"])
    op.create_index("idx_activity_events_media_type", "activity_events", ["media_type"])
    op.create_index("idx_activity_events_origin_id", "activity_events", ["origin_id"])
    op.create_index("idx_activity_events_reason", "activity_events", ["reason"])
    op.create_index("idx_activity_events_status", "activity_events", ["status"])
    op.create_index("idx_activity_events_time", "activity_events", ["time"])
    op.create_index("idx_activity_events_tmdb_id", "activity_events", ["tmdb_id"])
    op.create_index("idx_activity_events_trace_id", "activity_events", ["trace_id"])

    op.create_table(
        "transfer_jobs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("depot_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_transfer_jobs_created_at", "transfer_jobs", ["created_at"])
    op.create_index("idx_transfer_jobs_depot_id", "transfer_jobs", ["depot_id"])
    op.create_index("idx_transfer_jobs_requested_by", "transfer_jobs", ["requested_by"])
    op.create_index("idx_transfer_jobs_status", "transfer_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("transfer_jobs")
    op.drop_table("activity_events")
    op.drop_table("tmdb_detail_cache")
    op.drop_table("transfer_rules")
    op.drop_table("organize_rules")
    op.drop_table("origins")
    op.drop_table("depots")
    op.drop_table("watch_settings")
