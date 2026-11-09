"""Create the normalized Adaptive MVCC catalog tables.

Revision ID: 0001_initial_catalog
Revises:
"""
from alembic import op
from app.db.session import Base
from app.db import models  # noqa: F401 - registers all ORM tables

revision = "0001_initial_catalog"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
