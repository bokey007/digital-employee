"""add enum values

Revision ID: 64b0ebc20bca
Revises: 1f1bc84dae50
Create Date: 2026-02-26 11:16:40.699096

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64b0ebc20bca'
down_revision: Union[str, Sequence[str], None] = '1f1bc84dae50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE editionstatus ADD VALUE IF NOT EXISTS 'AWAITING_PROGRAMME_LEAD_APPROVAL'")
    op.execute("ALTER TYPE editionstatus ADD VALUE IF NOT EXISTS 'AWAITING_ASHWIN_APPROVAL'")
    op.execute("ALTER TYPE editionstatus ADD VALUE IF NOT EXISTS 'INCORPORATING_ASHWIN_FEEDBACK'")

    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'SENT_TO_PROGRAMME_LEAD'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'PROGRAMME_LEAD_APPROVED'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'PROGRAMME_LEAD_FEEDBACK'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'SENT_TO_ASHWIN'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'ASHWIN_APPROVED'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'ASHWIN_FEEDBACK'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
