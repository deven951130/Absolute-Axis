from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.config import SQLALCHEMY_DATABASE_URL

# SQLAlchemy Setup
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# ORM Models
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="Member")
    avatar = Column(String, default="")
    quota_bytes = Column(Integer, default=1073741824) # Default 1GB

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    username = Column(String, index=True)
    action = Column(String, nullable=False)

class FileStar(Base):
    __tablename__ = "file_stars"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    path = Column(String, index=True)

class FileShare(Base):
    __tablename__ = "file_shares"
    id = Column(Integer, primary_key=True, index=True)
    owner = Column(String, index=True)
    target = Column(String, index=True)
    path = Column(String, index=True)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
