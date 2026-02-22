from sqlalchemy import Column, Integer, Float, String, DateTime
from datetime import datetime
from .database import Base


class Investment(Base):
    __tablename__ = "investments"

    id = Column(Integer, primary_key=True, index=True)
    asset = Column(String, index=True)
    buy_price = Column(Float)
    invested_amount = Column(Float)
    quantity = Column(Float)
    purchase_date = Column(DateTime, default=datetime.utcnow)
    currency = Column(String, default="USD")

    # ÚJ MEZŐ
    usd_huf_rate_at_purchase = Column(Float)