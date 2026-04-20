"""attachment nullable message_id and add room_id

Revision ID: a1b2c3d4e5f6
Revises: 6c8b07407866
Create Date: 2026-04-20 12:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '6c8b07407866'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add room_id nullable first
    op.add_column('attachment', sa.Column('room_id', sa.Uuid(), nullable=True))
    # Backfill from message
    op.execute("UPDATE attachment a SET room_id = m.room_id FROM message m WHERE m.id = a.message_id")
    # Make NOT NULL
    op.alter_column('attachment', 'room_id', nullable=False)
    # FK and index for room_id
    op.create_foreign_key('fk_attachment_room_id', 'attachment', 'room', ['room_id'], ['id'])
    op.create_index(op.f('ix_attachment_room_id'), 'attachment', ['room_id'])
    # Make message_id nullable: drop FK + index, alter, recreate
    op.drop_constraint('attachment_message_id_fkey', 'attachment', type_='foreignkey')
    op.drop_index(op.f('ix_attachment_message_id'), table_name='attachment')
    op.alter_column('attachment', 'message_id', nullable=True)
    op.create_index(op.f('ix_attachment_message_id'), 'attachment', ['message_id'])
    op.create_foreign_key('fk_attachment_message_id', 'attachment', 'message', ['message_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_attachment_message_id', 'attachment', type_='foreignkey')
    op.drop_index(op.f('ix_attachment_message_id'), table_name='attachment')
    op.alter_column('attachment', 'message_id', nullable=False)
    op.create_index(op.f('ix_attachment_message_id'), 'attachment', ['message_id'])
    op.create_foreign_key('attachment_message_id_fkey', 'attachment', 'message', ['message_id'], ['id'])
    op.drop_constraint('fk_attachment_room_id', 'attachment', type_='foreignkey')
    op.drop_index(op.f('ix_attachment_room_id'), table_name='attachment')
    op.drop_column('attachment', 'room_id')
