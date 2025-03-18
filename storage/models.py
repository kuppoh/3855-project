import enum
from sqlalchemy.orm import DeclarativeBase, mapped_column
from sqlalchemy import Integer, String, DateTime, func, Enum ,ForeignKey, Float, DECIMAL, BigInteger

class Base(DeclarativeBase):
  pass

# Define the Python enum for listing status so that SQLAlchemy will recognize it
class ListingStatus(enum.Enum): 
  SOLD = "SOLD" 
  OFFER_PENDING = "OFFER_PENDING" 
  AVAILABLE = "AVAILABLE" 

class BiddingStatus(enum.Enum):
  APPROVED = "APPROVED"
  REJECTED = "REJECTED"

# change this to your actual shit
class listings(Base):
  __tablename__ = "listings"
  listing_id = mapped_column(Integer, primary_key=True)
  listing_price = mapped_column(DECIMAL(10,2), nullable=False)
  listing_post = mapped_column(DateTime, nullable=True, default=func.now())
  listing_type = mapped_column(String(50), nullable=False)
  listing_status = mapped_column(Enum(ListingStatus), nullable=False)
  listing_contact = mapped_column(String(254), nullable=False)
  trace_id = mapped_column(BigInteger, nullable=True)

class bids(Base):
  __tablename__ = "bids"
  bidding_id = mapped_column(Integer, primary_key=True)
  listing_id = mapped_column(Integer, ForeignKey('listings.listing_id'), nullable=False)
  asking_price = mapped_column(DECIMAL(10,2), nullable=False)
  offer_price = mapped_column(DECIMAL(10,2), nullable=True)
  offer_date = mapped_column(DateTime, nullable=False, default=func.now())
  property_square_feet = mapped_column(Integer, nullable=False)
  price_per_square_feet = mapped_column(DECIMAL(10,2), nullable=False)
  bid_status = mapped_column(Enum(BiddingStatus), nullable=False)
  trace_id = mapped_column(BigInteger, nullable=True)