"""Initialize database tables.
Run this script to ensure all tables, including the new CallLog table, are created.
"""
from app.infrastructure.database.connection import init_db
from app.domain.models.call import CallLog
from app.domain.models.chat import ChatMessage
from app.domain.models.user import User
from app.domain.models.log import DailyLog
from app.domain.models.placement import IndustrialPlacement

if __name__ == "__main__":
    print("Creating database tables...")
    init_db()
    print("Tables created successfully.")
