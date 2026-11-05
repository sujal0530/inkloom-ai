from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from .database import Base

class Rule(Base):
    __tablename__ = "rules"
    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True)
    text = Column(Text)
    category = Column(String(50))
    version = Column(Integer, default=1)

class Fact(Base):
    __tablename__ = "facts"
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True)
    value = Column(String(100))
    old_values = Column(JSON, default=list)

class Asset(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    content = Column(Text)
    status = Column(String(20), default="draft")
    flags = Column(JSON, default=list)
    seal = Column(String(64), nullable=True)
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rule_version = Column(Integer, nullable=True)