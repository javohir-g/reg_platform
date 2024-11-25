from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./clients.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Client(Base):
    __tablename__ = "clients"

    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    user_photo = Column(String)  # путь к файлу
    date_of_birth = Column(Date)
    user_passport_id = Column(String, unique=True, index=True)
    passport_photo = Column(String)  # путь к файлу
    user_phone_number = Column(String)
    migrating_country = Column(String)
    referral_for_tests = Column(String)  # путь к PDF
    reg_date = Column(DateTime, default=datetime.now)
    status = Column(Boolean, default=False)
    final_result = Column(String)  # путь к PDF
    assess = Column(Boolean, default=False)


Base.metadata.create_all(bind=engine)
