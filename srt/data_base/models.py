from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from srt.data_base.base import Base
from srt.config import MAX_CHAR_REQUIREMENTS, MAX_CHAR_RESUME

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True)

    requirements = relationship("Requirements", back_populates="user")
    resume = relationship("Resume", back_populates="user")

class Requirements(Base):
    __tablename__ = "requirements"
    requirements_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    requirements = Column(String(MAX_CHAR_REQUIREMENTS), nullable=False)

    user = relationship("User", back_populates="requirements")

class Resume(Base):
    __tablename__ = 'resume'
    resume_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    resume = Column(String(MAX_CHAR_RESUME), nullable=False)

    user = relationship("User", back_populates="resume")
