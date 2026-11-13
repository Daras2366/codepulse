"""add coach observability and feedback tables

Revision ID: d4e5f6a7b8c9
Revises: ef8dfd4a0607
Create Date: 2026-11-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'ef8dfd4a0607'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'coach_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('endpoint', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('tool_calls', sa.JSON(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('cache_hit', sa.Boolean(), nullable=False),
        sa.Column('error_kind', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_coach_runs_user_id'), 'coach_runs', ['user_id'], unique=False)

    op.create_table(
        'coach_recommendations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('problem_id', sa.Integer(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['coach_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['problem_id'], ['problems.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_coach_recommendations_run_id'), 'coach_recommendations', ['run_id'], unique=False)
    op.create_index(op.f('ix_coach_recommendations_user_id'), 'coach_recommendations', ['user_id'], unique=False)
    op.create_index(op.f('ix_coach_recommendations_problem_id'), 'coach_recommendations', ['problem_id'], unique=False)

    op.create_table(
        'coach_feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recommendation_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.Enum('solved', 'skipped', 'thumbs_up', 'thumbs_down', name='coachfeedbackaction'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['recommendation_id'], ['coach_recommendations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recommendation_id', 'action', name='uq_coach_feedback_rec_action'),
    )
    op.create_index(op.f('ix_coach_feedback_recommendation_id'), 'coach_feedback', ['recommendation_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_coach_feedback_recommendation_id'), table_name='coach_feedback')
    op.drop_table('coach_feedback')
    sa.Enum(
        'solved', 'skipped', 'thumbs_up', 'thumbs_down',
        name='coachfeedbackaction',
    ).drop(op.get_bind(), checkfirst=True)
    op.drop_index(op.f('ix_coach_recommendations_problem_id'), table_name='coach_recommendations')
    op.drop_index(op.f('ix_coach_recommendations_user_id'), table_name='coach_recommendations')
    op.drop_index(op.f('ix_coach_recommendations_run_id'), table_name='coach_recommendations')
    op.drop_table('coach_recommendations')
    op.drop_index(op.f('ix_coach_runs_user_id'), table_name='coach_runs')
    op.drop_table('coach_runs')
