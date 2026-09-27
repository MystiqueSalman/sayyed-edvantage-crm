"""phase 3: referrals, jobs, whatsapp

Revision ID: 68a1f67d1bff
Revises: b8e7da5a47e2
Create Date: 2026-09-27

Written explicitly (autogenerate ran after create_all and only saw the
index). Covers all Phase 3 tables + users.phone / users.referral_code.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '68a1f67d1bff'
down_revision = 'b8e7da5a47e2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('phone', sa.String(length=20),
                                      server_default='', nullable=True))
        batch_op.add_column(sa.Column('referral_code', sa.String(length=20),
                                      nullable=True))
        batch_op.create_index(batch_op.f('ix_users_referral_code'),
                              ['referral_code'], unique=True)

    op.create_table(
        'referral_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('reward_percent', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'))

    op.create_table(
        'referral_clicks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('ip_hash', sa.String(length=64), nullable=False),
        sa.Column('clicked_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', 'ip_hash', name='uq_click'))
    with op.batch_alter_table('referral_clicks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_referral_clicks_code'), ['code'],
                              unique=False)

    op.create_table(
        'referrals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('referrer_id', sa.Integer(), nullable=False),
        sa.Column('referred_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('coupon_code', sa.String(length=40), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('rewarded_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['referred_id'], ['users.id']),
        sa.ForeignKeyConstraint(['referrer_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('referred_id', name='uq_referred'))

    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('company', sa.String(length=160), nullable=True),
        sa.Column('type', sa.String(length=20), nullable=True),
        sa.Column('location', sa.String(length=160), nullable=True),
        sa.Column('remote', sa.Boolean(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('skills', sa.String(length=300), nullable=True),
        sa.Column('deadline', sa.Date(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.Column('apply_mode', sa.String(length=20), nullable=True),
        sa.Column('external_url', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'))

    op.create_table(
        'job_applications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('cover_note', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('applied_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id', 'user_id', name='uq_application'))

    op.create_table(
        'whatsapp_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone_number_id', sa.String(length=60), nullable=True),
        sa.Column('access_token', sa.String(length=255), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'))


def downgrade():
    op.drop_table('whatsapp_settings')
    op.drop_table('job_applications')
    op.drop_table('jobs')
    op.drop_table('referrals')
    with op.batch_alter_table('referral_clicks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_referral_clicks_code'))
    op.drop_table('referral_clicks')
    op.drop_table('referral_settings')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_referral_code'))
        batch_op.drop_column('referral_code')
        batch_op.drop_column('phone')
