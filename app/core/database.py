"""Database configuration"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Float
from datetime import datetime

from app.core.config import settings

# Database engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True
)

# Session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base model
Base = declarative_base()


class SessionLog(Base):
    """Terminal session logs"""
    __tablename__ = "session_logs"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), index=True)
    session_type = Column(String(50))
    user_id = Column(String(255), nullable=True)
    commands = Column(Text)
    output = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    duration = Column(Integer)
    status = Column(String(50))


class ToolExecution(Base):
    """Tool execution logs"""
    __tablename__ = "tool_executions"

    id = Column(Integer, primary_key=True)
    tool_name = Column(String(255))
    parameters = Column(JSON)
    result = Column(Text)
    execution_time = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50))


class FileOperation(Base):
    """File operation logs"""
    __tablename__ = "file_operations"

    id = Column(Integer, primary_key=True)
    operation = Column(String(50))
    path = Column(String(500))
    size = Column(Integer)
    user_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class InstalledTool(Base):
    """Installed tools tracking"""
    __tablename__ = "installed_tools"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True)
    manager = Column(String(50))
    version = Column(String(100))
    source = Column(String(500))
    installed_at = Column(DateTime, default=datetime.utcnow)
    path = Column(String(500))


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Get database session"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
