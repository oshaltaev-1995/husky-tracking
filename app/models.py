from __future__ import annotations

from sqlalchemy import (
    Column, Integer, String, Date, Float, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship

from app.db import Base


class Dog(Base):
    __tablename__ = "dogs"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True, index=True)

    training_logs = relationship("TrainingLog", back_populates="dog", cascade="all, delete-orphan")


class TrainingLog(Base):
    __tablename__ = "training_log"

    id = Column(Integer, primary_key=True)
    dog_id = Column(Integer, ForeignKey("dogs.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    distance_km = Column(Float, nullable=False)
    source = Column(String, nullable=False, default="excel")

    dog = relationship("Dog", back_populates="training_logs")

    __table_args__ = (
        UniqueConstraint("dog_id", "date", "source", name="uq_training_dog_date_source"),
        Index("ix_training_date_dog", "date", "dog_id"),
    )
