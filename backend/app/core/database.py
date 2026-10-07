"""
Database configuration and session management
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Create async engine
#
# `search_path` is not cosmetic — it is load-bearing. Supabase installs PostGIS
# into the `extensions` schema rather than `public`, and geoalchemy2 emits PostGIS
# function calls UNQUALIFIED: inserting into a Geography column renders as
# `ST_GeogFromText($1)`, with no schema. Without `extensions` on the path that
# fails with
#
#     function st_geogfromtext(unknown) does not exist
#
# and the insert is rolled back. This was latent until D01 because nothing had ever
# written to a geography column: `sos_incidents` was never populated (that was
# defect 35) and `user_locations` still is not. The first write found it.
#
# Set here, once, rather than qualified at each call site, because the call sites
# are inside geoalchemy2 and not ours to change. `public` stays first so nothing
# else resolves differently.
#
# Raw SQL in `app/scoring/surface_db.py` qualifies `extensions.ST_*` explicitly and
# does not depend on this. Belt and braces, deliberately: one of the two has to keep
# working if a pooled connection ever comes back with a different path.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"server_settings": {"search_path": "public,extensions"}},
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database"""
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
