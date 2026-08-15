"""
Database connection setup.
 
Purpose: create a single SQLAlchemy `engine` (the thing that actually talks
to Postgres) and a `SessionLocal` factory (creates one DB session per
request). FastAPI endpoints will depend on `get_db()` to borrow a session
and automatically close it when the request finishes.
"""
 
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Read the connection string from the environment (set in .env / Docker Compose).
# Never hardcode credentials in source — this is the one required piece of
# "security" the challenge calls out explicitly.
DATABASE_URL = os.environ["DATABASE_URL"]
 
# `engine`: manages the pool of actual connections to Postgres.
engine = create_engine(DATABASE_URL)
 
# `SessionLocal`: a factory that produces a new Session object each time
# it's called. autocommit/autoflush are left off so we control exactly
# when writes happen (inside crud.py functions).
SessionLocal = sessionmaker(autocommit = False,
                            autoflush = False,
                            bind = engine)
 
 
def get_db():
    """
    FastAPI dependency: yields a DB session for the duration of one request,
    then closes it — even if the request raised an exception. This is the
    standard FastAPI pattern for "give each request its own session, always
    clean up."
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
