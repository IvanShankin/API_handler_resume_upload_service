from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from srt.data_base.base import Base


class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True)

    requirements = relationship("Requirements", back_populates="user")
    resume = relationship("Resume", back_populates="user")

class Requirements(Base):
    __tablename__ = "requirements"
    requirements_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    requirements = Column(String(2000), nullable=False)

    user = relationship("User", back_populates="requirements")
    resume = relationship("Resume", back_populates="requirements")

class Resume(Base):
    __tablename__ = 'resume'
    resume_id = Column(Integer, primary_key=True, autoincrement=True)
    requirements_id = Column(Integer, ForeignKey("requirements.requirements_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    resume = Column(String(5000), nullable=False)

    user = relationship("User", back_populates="resume")
    requirements = relationship("Requirements", back_populates="resume")
