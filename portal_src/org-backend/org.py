from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks, Request
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator, Field
from typing import List, Optional, Dict, Any, Set, Annotated
from enum import Enum
import uuid
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal, ROUND_DOWN
import hashlib
import random
import json
import os
import sys
import asyncio

# Database imports
import asyncpg
from sqlalchemy import create_engine, Column, String, Integer, Numeric, DateTime, Date, Boolean, JSON, Text, ForeignKey, Enum as SQLEnum, CheckConstraint, Index, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship, declared_attr
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import text, select, update, delete
from contextlib import asynccontextmanager
import logging

# Redis for caching and queueing
import redis

# JWT for authentication
import jwt
from jwt import InvalidTokenError
import requests
import httpx

# FastAPI app setup
app = FastAPI(
    title="Democratic Economic System API",
    description="A complete democratic economic system with UBI, stock market, insurance, and fiscal policy",
    version="2.0.0"
)

# Security
security = HTTPBearer(auto_error=False)

# Database setup
DATABASE_URL = os.environ.get(
    "COCKROACH_DB_URL",
    "cockroachdb://root@cockroach:9000/defaultdb?sslmode=disable"
)

# For asyncpg direct connection (better for complex queries)
ASYNC_DB_URL = os.environ.get(
    "COCKROACH_ASYNC_URL",
    "postgresql://root@cockroach:9000/defaultdb?sslmode=disable"
)

# Redis for caching and queuing
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")

# JWT settings
PIDP_JWKS_URL = os.environ.get("PIDP_JWKS_URL", "http://pidp:8000/.well-known/jwks.json")
PIDP_BASE_URL = os.environ.get("PIDP_BASE_URL", "http://pidp:8000")
PIDP_JWT_ISSUER = os.environ.get("PIDP_JWT_ISSUER")
PIDP_JWT_AUDIENCE = os.environ.get("PIDP_JWT_AUDIENCE")

# SpiceDB (authorization)
SPICEDB_HTTP_URL = os.environ.get("SPICEDB_HTTP_URL", "http://spicedb:8443").rstrip("/")
SPICEDB_PRESHARED_KEY = os.environ.get("SPICEDB_PRESHARED_KEY", "")
ORG_ADMIN_GROUP = os.environ.get("ORG_ADMIN_GROUP", "admins")
ORG_RESOURCE_ID = os.environ.get("ORG_RESOURCE_ID", "portal")
ORG_ADMIN_USER_IDS = [
    item.strip()
    for item in os.environ.get("ORG_ADMIN_USER_IDS", "").split(",")
    if item.strip()
]

# System Constants
SYSTEM_CURRENCY = "DEM"
INITIAL_UBI_AMOUNT = Decimal('1000.00')
UBI_PAYMENT_CYCLE = 30
TAX_RATE_BASE = Decimal('0.15')
MINIMUM_WAGE = Decimal('15.00')
STOCK_MARKET_OPEN_HOUR = 9
STOCK_MARKET_CLOSE_HOUR = 17

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database Base
Base = declarative_base()

# ============= DATABASE MODELS =============

class EntityType(str, Enum):
    INDIVIDUAL = "individual"
    BUSINESS = "business"
    NONPROFIT = "nonprofit"
    GOVERNMENT = "government"

class InsuranceType(str, Enum):
    LIFE = "life"
    HEALTH = "health"
    FIRE = "fire"
    ACTS_OF_GOD = "acts_of_god"

class FiscalPolicyArea(str, Enum):
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    INFRASTRUCTURE = "infrastructure"
    DEFENSE = "defense"
    ENVIRONMENT = "environment"
    SOCIAL_WELFARE = "social_welfare"
    RESEARCH = "research"
    CULTURE = "culture"

class TransactionType(str, Enum):
    UBI_PAYMENT = "ubi_payment"
    TAX_PAYMENT = "tax_payment"
    SALARY = "salary"
    PURCHASE = "purchase"
    INVESTMENT = "investment"
    DIVIDEND = "dividend"
    INSURANCE_PREMIUM = "insurance_premium"
    INSURANCE_CLAIM = "insurance_claim"
    BUSINESS_REVENUE = "business_revenue"
    DONATION = "donation"
    GRANT = "grant"
    STOCK_PURCHASE = "stock_purchase"
    STOCK_SALE = "stock_sale"
    INTEREST = "interest"

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"

class OrderStatus(str, Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"

class VoteType(str, Enum):
    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"

class Account(Base):
    """Financial account for individuals, businesses, nonprofits, or government"""
    __tablename__ = "accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(SQLEnum(EntityType), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    address = Column(Text)
    balance = Column(Numeric(20, 2), nullable=False, default=Decimal('0.00'))
    credit_score = Column(Integer, nullable=False, default=650)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # Business/nonprofit specific
    business_type = Column(String(100))
    mission_statement = Column(Text)
    tax_id = Column(String(50), unique=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_accounts_email', 'email'),
        Index('idx_accounts_entity_type', 'entity_type'),
        Index('idx_accounts_created_at', 'created_at'),
        CheckConstraint('balance >= 0', name='check_balance_non_negative'),
        CheckConstraint('credit_score >= 300 AND credit_score <= 850', name='check_credit_score_range'),
    )
    
    # Relationships
    transactions_from = relationship("Transaction", foreign_keys="Transaction.from_account_id", back_populates="from_account")
    transactions_to = relationship("Transaction", foreign_keys="Transaction.to_account_id", back_populates="to_account")
    portfolio = relationship("PortfolioHolding", back_populates="account")
    insurance_policies = relationship("InsurancePolicy", back_populates="account")
    fiscal_votes = relationship("FiscalVote", back_populates="account")
    edit_requests = relationship(
        "EditRequest",
        foreign_keys="EditRequest.account_id",
        back_populates="account",
    )

class Transaction(Base):
    """Financial transaction record with double-entry accounting"""
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_account_id = Column(UUID(as_uuid=True), ForeignKey('accounts.id', ondelete='SET NULL'), index=True)
    to_account_id = Column(UUID(as_uuid=True), ForeignKey('accounts.id', ondelete='SET NULL'), index=True)
    amount = Column(Numeric(20, 2), nullable=False)
    currency = Column(String(3), nullable=False, default=SYSTEM_CURRENCY)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False, index=True)
    description = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)
    reference_id = Column(String(100))  # For linking to other entities
    tx_metadata = Column("metadata", JSONB)  # Additional transaction data
    
    # Indexes
    __table_args__ = (
        Index('idx_transactions_timestamp', 'timestamp'),
        Index('idx_transactions_from_account', 'from_account_id', 'timestamp'),
        Index('idx_transactions_to_account', 'to_account_id', 'timestamp'),
        Index('idx_transactions_type', 'transaction_type', 'timestamp'),
        CheckConstraint('amount > 0', name='check_amount_positive'),
    )
    
    # Relationships
    from_account = relationship("Account", foreign_keys=[from_account_id], back_populates="transactions_from")
    to_account = relationship("Account", foreign_keys=[to_account_id], back_populates="transactions_to")

class UBIEligibility(Base):
    """Universal Basic Income eligibility and payment tracking"""
    __tablename__ = "ubi_eligibility"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey('accounts.id', ondelete='CASCADE'), unique=True, nullable=False)
    is_eligible = Column(Boolean, nullable=False, default=True)
    next_payment_date = Column(Date, nullable=False)
    last_payment_date = Column(Date)
    last_payment_amount = Column(Numeric(20, 2))
    total_payments_received = Column(Numeric(20, 2), default=Decimal('0.00'))
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_ubi_eligibility_next_payment', 'next_payment_date', 'is_eligible'),
        Index('idx_ubi_eligibility_account', 'account_id'),
    )
    
    # Relationships
    account = relationship("Account")

class Stock(Base):
    """Publicly traded company stock"""
    __tablename__ = "stocks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(255), nullable=False)
    ticker_symbol = Column(String(10), nullable=False, unique=True, index=True)
    current_price = Column(Numeric(20, 2), nullable=False)
    day_open = Column(Numeric(20, 2), nullable=False)
    day_high = Column(Numeric(20, 2), nullable=False)
    day_low = Column(Numeric(20, 2), nullable=False)
    volume = Column(Integer, nullable=False, default=0)
    total_shares = Column(Integer, nullable=False)
    shares_outstanding = Column(Integer, nullable=False)
    market_cap = Column(Numeric(20, 2), nullable=False)
    sector = Column(String(100), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    last_updated = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_stocks_ticker', 'ticker_symbol'),
        Index('idx_stocks_sector', 'sector'),
        Index('idx_stocks_active', 'is_active'),
        CheckConstraint('current_price > 0', name='check_price_positive'),
        CheckConstraint('shares_outstanding <= total_shares', name='check_shares_outstanding'),
    )
    
    # Relationships
    holdings = relationship("PortfolioHolding", back_populates="stock")
    orders = relationship("StockOrder", back_populates="stock")

class PortfolioHolding(Base):
    """Stock holdings in accounts"""
    __tablename__ = "portfolio_holdings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    stock_id = Column(UUID(as_uuid=True), ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    average_purchase_price = Column(Numeric(20, 2))
    total_invested = Column(Numeric(20, 2), default=Decimal('0.00'))
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # Composite unique constraint
    __table_args__ = (
        Index('idx_portfolio_account_stock', 'account_id', 'stock_id', unique=True),
        Index('idx_portfolio_account', 'account_id'),
        CheckConstraint('quantity >= 0', name='check_quantity_non_negative'),
    )
    
    # Relationships
    account = relationship("Account", back_populates="portfolio")
    stock = relationship("Stock", back_populates="holdings")

class StockOrder(Base):
    """Stock market orders"""
    __tablename__ = "stock_orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    stock_id = Column(UUID(as_uuid=True), ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False)
    order_type = Column(SQLEnum(OrderType), nullable=False)
    action = Column(String(4), nullable=False)  # 'buy' or 'sell'
    quantity = Column(Integer, nullable=False)
    limit_price = Column(Numeric(20, 2))
    status = Column(SQLEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    executed_price = Column(Numeric(20, 2))
    executed_quantity = Column(Integer, default=0)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)
    executed_at = Column(DateTime(timezone=True))
    
    # Indexes
    __table_args__ = (
        Index('idx_orders_account', 'account_id', 'timestamp'),
        Index('idx_orders_stock', 'stock_id', 'timestamp'),
        Index('idx_orders_status', 'status', 'timestamp'),
        CheckConstraint('quantity > 0', name='check_quantity_positive'),
        CheckConstraint("action IN ('buy', 'sell')", name='check_action_valid'),
    )
    
    # Relationships
    account = relationship("Account")
    stock = relationship("Stock", back_populates="orders")

class InsurancePolicy(Base):
    """Insurance policies"""
    __tablename__ = "insurance_policies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    insurance_type = Column(SQLEnum(InsuranceType), nullable=False)
    coverage_amount = Column(Numeric(20, 2), nullable=False)
    premium_amount = Column(Numeric(20, 2), nullable=False)
    duration_years = Column(Integer, nullable=False, default=1)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    beneficiaries = Column(JSONB)  # List of beneficiary account IDs
    deductible = Column(Numeric(20, 2), default=Decimal('0.00'))
    claims_made = Column(Integer, nullable=False, default=0)
    total_claims_paid = Column(Numeric(20, 2), default=Decimal('0.00'))
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_insurance_account', 'account_id'),
        Index('idx_insurance_type', 'insurance_type'),
        Index('idx_insurance_active', 'is_active', 'end_date'),
        CheckConstraint('coverage_amount > 0', name='check_coverage_positive'),
        CheckConstraint('premium_amount > 0', name='check_premium_positive'),
    )
    
    # Relationships
    account = relationship("Account", back_populates="insurance_policies")
    claims = relationship("InsuranceClaim", back_populates="policy")

class InsuranceClaim(Base):
    """Insurance claims"""
    __tablename__ = "insurance_claims"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey('insurance_policies.id', ondelete='CASCADE'), nullable=False)
    claim_amount = Column(Numeric(20, 2), nullable=False)
    approved_amount = Column(Numeric(20, 2))
    description = Column(Text, nullable=False)
    incident_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default='pending')  # pending, approved, rejected, paid
    supporting_docs = Column(JSONB)  # List of document URLs
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey('accounts.id'))
    reviewed_at = Column(DateTime(timezone=True))
    paid_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_claims_policy', 'policy_id'),
        Index('idx_claims_status', 'status', 'created_at'),
        CheckConstraint('claim_amount > 0', name='check_claim_amount_positive'),
    )
    
    # Relationships
    policy = relationship("InsurancePolicy", back_populates="claims")
    reviewer = relationship("Account", foreign_keys=[reviewed_by])

class FiscalProposal(Base):
    """Fiscal policy proposals for democratic voting"""
    __tablename__ = "fiscal_proposals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    policy_area = Column(SQLEnum(FiscalPolicyArea), nullable=False, index=True)
    proposed_budget = Column(Numeric(20, 2), nullable=False)
    duration_months = Column(Integer, nullable=False)
    expected_impact = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey('accounts.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    voting_start = Column(DateTime(timezone=True))
    voting_end = Column(DateTime(timezone=True))
    status = Column(String(20), nullable=False, default='draft')  # draft, voting, passed, rejected, implemented
    yes_votes = Column(Integer, default=0)
    no_votes = Column(Integer, default=0)
    abstain_votes = Column(Integer, default=0)
    total_votes = Column(Integer, default=0)
    
    # Indexes
    __table_args__ = (
        Index('idx_proposals_status', 'status', 'voting_end'),
        Index('idx_proposals_policy_area', 'policy_area'),
        Index('idx_proposals_created_at', 'created_at'),
        CheckConstraint('proposed_budget > 0', name='check_budget_positive'),
    )
    
    # Relationships
    creator = relationship("Account")
    votes = relationship("FiscalVote", back_populates="proposal")

class FiscalVote(Base):
    """Votes on fiscal proposals"""
    __tablename__ = "fiscal_votes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id = Column(UUID(as_uuid=True), ForeignKey('fiscal_proposals.id', ondelete='CASCADE'), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    vote = Column(SQLEnum(VoteType), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())
    rationale = Column(Text)
    
    # Composite unique constraint - one vote per account per proposal
    __table_args__ = (
        Index('idx_votes_proposal_account', 'proposal_id', 'account_id', unique=True),
        Index('idx_votes_account', 'account_id'),
        Index('idx_votes_proposal', 'proposal_id'),
    )
    
    # Relationships
    proposal = relationship("FiscalProposal", back_populates="votes")
    account = relationship("Account", back_populates="fiscal_votes")

class BudgetAllocation(Base):
    """Government budget allocations"""
    __tablename__ = "budget_allocations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fiscal_year = Column(Integer, nullable=False)
    policy_area = Column(SQLEnum(FiscalPolicyArea), nullable=False)
    allocated_amount = Column(Numeric(20, 2), nullable=False)
    spent_amount = Column(Numeric(20, 2), default=Decimal('0.00'))
    percentage = Column(Numeric(5, 2))  # Percentage of total budget
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # Composite unique constraint
    __table_args__ = (
        Index('idx_budget_fiscal_year', 'fiscal_year', 'policy_area', unique=True),
        Index('idx_budget_policy_area', 'policy_area'),
        CheckConstraint('allocated_amount >= 0', name='check_allocated_non_negative'),
        CheckConstraint('spent_amount >= 0', name='check_spent_non_negative'),
    )

class TaxRecord(Base):
    """Tax payment records"""
    __tablename__ = "tax_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    tax_year = Column(Integer, nullable=False)
    taxable_income = Column(Numeric(20, 2), nullable=False)
    tax_amount = Column(Numeric(20, 2), nullable=False)
    paid_amount = Column(Numeric(20, 2), default=Decimal('0.00'))
    status = Column(String(20), nullable=False, default='unpaid')  # unpaid, partial, paid
    due_date = Column(Date, nullable=False)
    paid_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_tax_account_year', 'account_id', 'tax_year', unique=True),
        Index('idx_tax_status_due', 'status', 'due_date'),
        CheckConstraint('taxable_income >= 0', name='check_income_non_negative'),
        CheckConstraint('tax_amount >= 0', name='check_tax_non_negative'),
    )
    
    # Relationships
    account = relationship("Account")

class EditRequest(Base):
    """Request to edit account information (for KYC/verification)"""
    __tablename__ = "edit_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default='pending')  # pending, approved, rejected
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey('accounts.id'))
    reviewed_at = Column(DateTime(timezone=True))
    message = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_edit_requests_account', 'account_id', 'status'),
        Index('idx_edit_requests_status', 'status', 'created_at'),
    )
    
    # Relationships
    account = relationship(
        "Account",
        foreign_keys=[account_id],
        back_populates="edit_requests",
    )
    reviewer = relationship("Account", foreign_keys=[reviewed_by])

# ============= PYDANTIC MODELS =============

class AccountCreate(BaseModel):
    entity_type: EntityType
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    address: Optional[str] = None
    business_type: Optional[str] = None
    mission_statement: Optional[str] = None
    initial_deposit: Decimal = Field(Decimal('0.00'), ge=0)

class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = None
    business_type: Optional[str] = None
    mission_statement: Optional[str] = None

class AccountResponse(BaseModel):
    id: uuid.UUID
    entity_type: EntityType
    name: str
    email: str
    address: Optional[str]
    balance: Decimal
    credit_score: int
    created_at: datetime
    business_type: Optional[str] = None
    mission_statement: Optional[str] = None
    tax_id: Optional[str] = None
    is_verified: bool
    
    class Config:
        from_attributes = True

class AccountListItemResponse(BaseModel):
    id: uuid.UUID
    entity_type: EntityType
    name: str
    email: str
    balance: Decimal
    created_at: datetime

    class Config:
        from_attributes = True

class MoneySupplyPointResponse(BaseModel):
    timestamp: datetime
    total_supply: Decimal

class MoneySupplyHistoryResponse(BaseModel):
    points: List[MoneySupplyPointResponse]
    current_total_supply: Decimal
    currency: str

class TransactionCreate(BaseModel):
    to_account_id: Optional[uuid.UUID] = None
    amount: Decimal = Field(..., gt=0)
    transaction_type: TransactionType
    description: str
    reference_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class TransactionResponse(BaseModel):
    id: uuid.UUID
    from_account_id: Optional[uuid.UUID]
    to_account_id: Optional[uuid.UUID]
    amount: Decimal
    currency: str
    transaction_type: TransactionType
    description: str
    timestamp: datetime
    reference_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(None, alias="tx_metadata")
    
    class Config:
        from_attributes = True
        allow_population_by_field_name = True

class RecentTransactionResponse(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    transaction_type: TransactionType
    amount: Decimal
    currency: str
    description: str
    from_account_id: Optional[uuid.UUID] = None
    to_account_id: Optional[uuid.UUID] = None
    from_account_name: Optional[str] = None
    to_account_name: Optional[str] = None

class AccountAutomationResponse(BaseModel):
    account_id: uuid.UUID
    name: str
    email: str
    balance: Decimal
    currency: str
    account_endpoint: str
    incoming_transactions_endpoint: str
    all_transactions_endpoint: str
    send_payment_endpoint: str
    send_url_template: str
    updated_at: datetime

class StockCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    ticker_symbol: str = Field(..., min_length=1, max_length=10, pattern=r'^[A-Z]{1,10}$')
    total_shares: int = Field(..., gt=0)
    initial_price: Decimal = Field(..., gt=0)
    sector: str
    description: Optional[str] = None

class StockOrderCreate(BaseModel):
    stock_id: uuid.UUID
    quantity: int = Field(..., gt=0)
    order_type: OrderType
    limit_price: Optional[Decimal] = Field(None, gt=0)
    action: str = Field(..., pattern='^(buy|sell)$')

class InsurancePolicyCreate(BaseModel):
    insurance_type: InsuranceType
    coverage_amount: Decimal = Field(..., gt=0)
    duration_years: int = Field(1, ge=1, le=30)
    beneficiaries: Optional[List[uuid.UUID]] = None
    deductible: Optional[Decimal] = Field(None, ge=0)

class InsuranceClaimCreate(BaseModel):
    policy_id: uuid.UUID
    claim_amount: Decimal = Field(..., gt=0)
    description: str
    incident_date: date
    supporting_docs: Optional[List[str]] = None

class FiscalProposalCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str
    policy_area: FiscalPolicyArea
    proposed_budget: Decimal = Field(..., gt=0)
    duration_months: int = Field(..., gt=0, le=120)
    expected_impact: str
    voting_days: int = Field(7, ge=1, le=30)

class FiscalVoteCreate(BaseModel):
    vote: VoteType
    rationale: Optional[str] = None

class TaxEstimate(BaseModel):
    taxable_income: Decimal = Field(..., ge=0)
    tax_year: int

class UBIRuntimeSettingsResponse(BaseModel):
    interval_seconds: int
    dena_annual: Decimal
    dena_precision: int
    entity_types: List[str]
    updated_at: datetime
    updated_by: Optional[str] = None

class UBIRuntimeSettingsUpdate(BaseModel):
    interval_seconds: Optional[int] = Field(None, ge=1, le=86400)
    dena_annual: Optional[Decimal] = Field(None, ge=Decimal("0"))
    dena_precision: Optional[int] = Field(None, ge=0, le=12)
    entity_types: Optional[List[str]] = None

    @validator("entity_types")
    def validate_entity_types(cls, value):
        if value is None:
            return value
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("entity_types must contain at least one value")
        return cleaned

# ============= DATABASE DEPENDENCY =============

class Database:
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self.redis_client = None
        self.async_pool = None
    
    async def connect(self):
        """Initialize database connections"""
        try:
            # SQLAlchemy engine for synchronous operations
            self.engine = create_engine(
                DATABASE_URL,
                pool_size=20,
                max_overflow=30,
                pool_pre_ping=True,
                echo=False
            )
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            
            # Asyncpg pool for complex async operations
            self.async_pool = await asyncpg.create_pool(
                ASYNC_DB_URL,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            
            # Redis client for caching
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD if REDIS_PASSWORD else None,
                decode_responses=True
            )
            
            logger.info("Database connections established")
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    async def disconnect(self):
        """Close database connections"""
        if self.async_pool:
            await self.async_pool.close()
        if self.engine:
            self.engine.dispose()
        if self.redis_client:
            self.redis_client.close()
        logger.info("Database connections closed")
    
    def get_session(self):
        """Get database session for dependency injection"""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    async def get_async_conn(self):
        """Get async database connection"""
        async with self.async_pool.acquire() as conn:
            yield conn

# Initialize database
db = Database()

DEFAULT_UBI_INTERVAL_SECONDS = int(os.environ.get("UBI_INTERVAL_SECONDS", "60"))
DEFAULT_DENA_ANNUAL = Decimal(os.environ.get("DENA_ANNUAL", "1"))
DEFAULT_DENA_PRECISION = int(os.environ.get("DENA_PRECISION", "6"))
DEFAULT_UBI_ENTITY_TYPES = [
    item.strip()
    for item in os.environ.get("UBI_ENTITY_TYPES", "individual").split(",")
    if item.strip()
]


async def ensure_ubi_runtime_settings_table() -> None:
    entity_csv = ",".join(DEFAULT_UBI_ENTITY_TYPES or ["individual"])
    async with db.async_pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ubi_runtime_settings (
                id INT PRIMARY KEY CHECK (id = 1),
                interval_seconds INT NOT NULL,
                dena_annual DECIMAL(20, 6) NOT NULL,
                dena_precision INT NOT NULL,
                entity_types TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_by TEXT
            )
            """
        )
        await conn.execute(
            """
            INSERT INTO ubi_runtime_settings (id, interval_seconds, dena_annual, dena_precision, entity_types, updated_by)
            VALUES (1, $1, $2, $3, $4, 'org-backend-bootstrap')
            ON CONFLICT (id) DO NOTHING
            """,
            DEFAULT_UBI_INTERVAL_SECONDS,
            float(DEFAULT_DENA_ANNUAL),
            DEFAULT_DENA_PRECISION,
            entity_csv,
        )


def _default_ubi_runtime_settings() -> dict:
    return {
        "interval_seconds": DEFAULT_UBI_INTERVAL_SECONDS,
        "dena_annual": DEFAULT_DENA_ANNUAL,
        "dena_precision": DEFAULT_DENA_PRECISION,
        "entity_types": DEFAULT_UBI_ENTITY_TYPES or ["individual"],
        "updated_at": datetime.now(timezone.utc),
        "updated_by": None,
    }


def _parse_entity_types_csv(value: str) -> list[str]:
    parsed = [item.strip() for item in (value or "").split(",") if item.strip()]
    return parsed or ["individual"]


async def get_ubi_runtime_settings() -> dict:
    try:
        await ensure_ubi_runtime_settings_table()
        async with db.async_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT interval_seconds, dena_annual, dena_precision, entity_types, updated_at, updated_by
                FROM ubi_runtime_settings
                WHERE id = 1
                """
            )
    except Exception as exc:
        logger.warning(f"UBI runtime settings unavailable, using defaults: {exc}")
        return _default_ubi_runtime_settings()
    if not row:
        return _default_ubi_runtime_settings()
    return {
        "interval_seconds": int(row["interval_seconds"]),
        "dena_annual": Decimal(str(row["dena_annual"])),
        "dena_precision": int(row["dena_precision"]),
        "entity_types": _parse_entity_types_csv(str(row["entity_types"])),
        "updated_at": row["updated_at"],
        "updated_by": row["updated_by"],
    }


def _spicedb_enabled() -> bool:
    return bool(SPICEDB_HTTP_URL and SPICEDB_PRESHARED_KEY)


def _spicedb_headers() -> dict:
    return {"Authorization": f"Bearer {SPICEDB_PRESHARED_KEY}"}


def _spicedb_relationship(
    resource_type: str,
    resource_id: str,
    relation: str,
    subject_type: str,
    subject_id: str,
    subject_relation: str | None = None,
) -> dict:
    relationship = {
        "resource": {"objectType": resource_type, "objectId": resource_id},
        "relation": relation,
        "subject": {
            "object": {"objectType": subject_type, "objectId": subject_id},
        },
    }
    if subject_relation:
        relationship["subject"]["optionalRelation"] = subject_relation
    return relationship


async def _spicedb_read_schema() -> str:
    if not _spicedb_enabled():
        return ""
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(
            f"{SPICEDB_HTTP_URL}/v1/schema/read",
            headers=_spicedb_headers(),
        )
    if not resp.is_success:
        return ""
    data = resp.json()
    return data.get("schema_text", "") or ""


async def _spicedb_write_schema() -> None:
    if not _spicedb_enabled():
        return
    current_schema = await _spicedb_read_schema()
    parts: list[str] = []
    if "definition user" not in current_schema:
        parts.append("definition user {}")
    if "definition group" not in current_schema:
        parts.append("definition group { relation member: user }")
    if "definition org" not in current_schema:
        parts.append(
            "definition org { relation admin: user | group#member\n  permission db_admin = admin }"
        )
    if not parts:
        return
    next_schema = current_schema.rstrip()
    if next_schema:
        next_schema += "\n\n"
    next_schema += "\n\n".join(parts)
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(
            f"{SPICEDB_HTTP_URL}/v1/schema/write",
            headers=_spicedb_headers(),
            json={"schema": next_schema},
        )


async def _spicedb_write_relationships(relationships: list[dict]) -> None:
    if not _spicedb_enabled() or not relationships:
        return
    updates = [
        {
            "operation": "OPERATION_TOUCH",
            "relationship": relationship,
        }
        for relationship in relationships
    ]
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(
            f"{SPICEDB_HTTP_URL}/v1/relationships/write",
            headers=_spicedb_headers(),
            json={"updates": updates},
        )


async def _spicedb_check_admin(user_id: str) -> bool:
    if not _spicedb_enabled():
        return False
    payload = {
        "resource": {"objectType": "org", "objectId": ORG_RESOURCE_ID},
        "permission": "db_admin",
        "subject": {"object": {"objectType": "user", "objectId": user_id}},
    }
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.post(
            f"{SPICEDB_HTTP_URL}/v1/permissions/check",
            headers=_spicedb_headers(),
            json=payload,
        )
    if not resp.is_success:
        return False
    data = resp.json()
    return data.get("permissionship") == "PERMISSIONSHIP_HAS_PERMISSION"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for startup/shutdown"""
    await db.connect()
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=db.engine)
    logger.info("Database tables verified/created")
    await ensure_ubi_runtime_settings_table()

    # SpiceDB schema + admin bootstrap
    try:
        await _spicedb_write_schema()
        relationships: list[dict] = [
            _spicedb_relationship(
                "org",
                ORG_RESOURCE_ID,
                "admin",
                "group",
                ORG_ADMIN_GROUP,
                "member",
            )
        ]
        for admin_id in ORG_ADMIN_USER_IDS:
            relationships.append(
                _spicedb_relationship("group", ORG_ADMIN_GROUP, "member", "user", admin_id)
            )
        await _spicedb_write_relationships(relationships)
    except Exception as exc:
        logger.warning(f"SpiceDB bootstrap skipped: {exc}")
    
    yield
    
    await db.disconnect()

app = FastAPI(lifespan=lifespan)

# Dependency for database session
def get_db():
    session = db.SessionLocal()
    try:
        yield session
    finally:
        session.close()

# Dependency for async database connection
async def get_async_db():
    async with db.async_pool.acquire() as conn:
        yield conn

# ============= AUTHENTICATION =============

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_db)
):
    if not credentials:
        # For demo purposes, allow anonymous users with limited access
        return {"id": str(uuid.uuid4()), "email": "anonymous@demo.com", "name": "Anonymous", "is_anonymous": True, "is_admin": False}
    
    token = credentials.credentials
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{PIDP_BASE_URL}/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        if not resp.is_success:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        pidp_user = resp.json()
        user_id = str(pidp_user.get("id"))
        email = pidp_user.get("email")
        name = pidp_user.get("full_name") or email or "User"
        if not user_id or not email:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Find or create account
        account = session.query(Account).filter_by(email=email).first()
        if not account:
            account = Account(
                id=uuid.uuid4(),
                entity_type=EntityType.INDIVIDUAL,
                name=name,
                email=email,
                balance=Decimal('10000.00')
            )
            session.add(account)
            session.commit()

        # Allow an explicit env-based admin override for recovery/bootstrap.
        # This keeps admin access possible even if SpiceDB is unavailable/misconfigured.
        is_admin = user_id in ORG_ADMIN_USER_IDS or await _spicedb_check_admin(user_id)
        return {
            "id": str(account.id),
            "email": account.email,
            "name": account.name,
            "is_anonymous": False,
            "is_admin": is_admin,
            "pidp_id": user_id,
        }
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

# ============= ECONOMIC ENGINE =============

class EconomicEngine:
    @staticmethod
    def calculate_tax(income: Decimal, entity_type: EntityType) -> Decimal:
        """Calculate tax with progressive rates"""
        if entity_type == EntityType.NONPROFIT:
            return Decimal('0.00')
        
        tax_brackets = [
            (Decimal('0.00'), Decimal('25000.00'), Decimal('0.10')),
            (Decimal('25000.01'), Decimal('50000.00'), Decimal('0.15')),
            (Decimal('50000.01'), Decimal('100000.00'), Decimal('0.20')),
            (Decimal('100000.01'), Decimal('500000.00'), Decimal('0.25')),
            (Decimal('500000.01'), None, Decimal('0.30')),
        ]
        
        tax = Decimal('0.00')
        remaining_income = income
        
        for lower, upper, rate in tax_brackets:
            if remaining_income <= Decimal('0.00'):
                break
            
            if upper is None or remaining_income <= (upper - lower):
                tax += remaining_income * rate
                break
            else:
                bracket_income = upper - lower
                tax += bracket_income * rate
                remaining_income -= bracket_income
        
        return tax.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    
    @staticmethod
    def calculate_insurance_premium(
        insurance_type: InsuranceType,
        coverage_amount: Decimal,
        risk_factors: Dict[str, Any]
    ) -> Decimal:
        """Calculate insurance premium based on risk factors"""
        base_rates = {
            InsuranceType.LIFE: Decimal('0.0005'),  # 0.05% per year
            InsuranceType.HEALTH: Decimal('0.01'),   # 1% per year
            InsuranceType.FIRE: Decimal('0.0015'),   # 0.15% per year
            InsuranceType.ACTS_OF_GOD: Decimal('0.002'),  # 0.2% per year
        }
        
        base_premium = coverage_amount * base_rates[insurance_type]
        
        # Apply risk factors
        risk_multiplier = Decimal('1.0')
        
        if insurance_type == InsuranceType.LIFE:
            age = risk_factors.get('age', 35)
            if age > 60:
                risk_multiplier *= Decimal('2.5')
            elif age > 45:
                risk_multiplier *= Decimal('1.5')
            elif age < 25:
                risk_multiplier *= Decimal('0.7')
        
        elif insurance_type == InsuranceType.HEALTH:
            health_score = risk_factors.get('health_score', 75)
            if health_score < 50:
                risk_multiplier *= Decimal('2.0')
            elif health_score > 85:
                risk_multiplier *= Decimal('0.8')
        
        elif insurance_type == InsuranceType.FIRE:
            location_risk = risk_factors.get('location_risk', 'medium')
            if location_risk == 'high':
                risk_multiplier *= Decimal('2.0')
            elif location_risk == 'low':
                risk_multiplier *= Decimal('0.8')
        
        return (base_premium * risk_multiplier).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    
    @staticmethod
    def calculate_stock_price_variation(
        current_price: Decimal,
        volume: int,
        market_sentiment: Decimal,
        volatility: Decimal = Decimal('0.02')
    ) -> Decimal:
        """Calculate stock price variation using geometric Brownian motion"""
        import random
        import math
        
        # Random component (Wiener process)
        z = Decimal(str(random.gauss(0, 1)))
        
        # Drift based on market sentiment (0 to 1 scale, where 0.5 is neutral)
        drift = (market_sentiment - Decimal('0.5')) * Decimal('0.01')
        
        # Volatility adjustment based on volume
        volume_factor = Decimal(str(min(math.log(volume + 1) / 10, 0.1)))
        
        # Calculate price change
        price_change = drift + (volatility * z) + volume_factor
        
        # Apply change with bounds
        new_price = current_price * (Decimal('1.0') + price_change)
        
        # Ensure price doesn't drop below minimum
        min_price = current_price * Decimal('0.01')  # Minimum 1% of current price
        return max(new_price, min_price).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

# ============= ACCOUNT ENDPOINTS =============

@app.post("/api/accounts", response_model=AccountResponse)
async def create_account(
    account_data: AccountCreate,
    session: Session = Depends(get_db)
):
    """Create a new financial account"""
    # Check if email already exists
    existing = session.query(Account).filter_by(email=account_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Generate tax ID for businesses/nonprofits
    tax_id = None
    if account_data.entity_type in [EntityType.BUSINESS, EntityType.NONPROFIT]:
        tax_id = f"TX{hashlib.md5(account_data.email.encode()).hexdigest()[:10].upper()}"
    
    # Create account
    account = Account(
        id=uuid.uuid4(),
        entity_type=account_data.entity_type,
        name=account_data.name,
        email=account_data.email,
        address=account_data.address,
        balance=Decimal('0.00'),
        business_type=account_data.business_type,
        mission_statement=account_data.mission_statement,
        tax_id=tax_id
    )
    
    session.add(account)
    
    # Create UBI eligibility if individual
    if account_data.entity_type == EntityType.INDIVIDUAL:
        ubi = UBIEligibility(
            id=uuid.uuid4(),
            account_id=account.id,
            next_payment_date=date.today() + timedelta(days=UBI_PAYMENT_CYCLE),
            is_eligible=True
        )
        session.add(ubi)
    
    session.commit()
    session.refresh(account)
    
    return account

@app.get("/api/accounts/me", response_model=AccountResponse)
async def get_my_account(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Get current user's account"""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return account

@app.get("/api/accounts/me/automation", response_model=AccountAutomationResponse)
async def get_my_account_automation(
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Automation-friendly account discovery endpoint for receive/payment workflows."""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")

    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    base = str(request.base_url).rstrip("/")
    return {
        "account_id": account.id,
        "name": account.name,
        "email": account.email,
        "balance": account.balance,
        "currency": SYSTEM_CURRENCY,
        "account_endpoint": f"{base}/api/accounts/me",
        "incoming_transactions_endpoint": f"{base}/api/accounts/me/transactions/incoming?limit=50",
        "all_transactions_endpoint": f"{base}/api/accounts/me/transactions?limit=50",
        "send_payment_endpoint": f"{base}/api/transactions",
        "send_url_template": f"{base}/send?to={account.id}&amount={{amount}}",
        "updated_at": account.updated_at,
    }

@app.get("/api/accounts/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: uuid.UUID,
    session: Session = Depends(get_db)
):
    """Get account by ID"""
    account = session.query(Account).filter_by(id=account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return account

@app.get("/api/accounts", response_model=List[AccountListItemResponse])
async def list_accounts(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db),
    q: str = "",
    sort: str = "balance_desc",
    limit: int = 500,
):
    """List accounts for directory/search views."""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")

    safe_limit = max(1, min(limit, 2000))
    query = session.query(Account)

    if q.strip():
        needle = f"%{q.strip()}%"
        query = query.filter(
            (Account.name.ilike(needle)) | (Account.email.ilike(needle))
        )

    if sort == "balance_asc":
        query = query.order_by(Account.balance.asc(), Account.name.asc())
    elif sort == "name_asc":
        query = query.order_by(Account.name.asc())
    elif sort == "name_desc":
        query = query.order_by(Account.name.desc())
    else:
        query = query.order_by(Account.balance.desc(), Account.name.asc())

    return query.limit(safe_limit).all()

@app.get("/admin/me")
async def get_admin_status(current_user: dict = Depends(get_current_user)):
    """Check if current user is an admin."""
    if current_user.get("is_anonymous"):
        return {"is_admin": False}
    return {"is_admin": current_user.get("is_admin", False)}

@app.get("/api/admin/accounts", response_model=List[AccountListItemResponse])
async def list_admin_accounts(
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_db),
):
    """List admin accounts by resolving PIDP users and SpiceDB admin membership."""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    token = credentials.credentials
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{PIDP_BASE_URL}/auth/users",
                params={"email": "%"},
                headers={"Authorization": f"Bearer {token}"},
            )
        if not resp.is_success:
            raise HTTPException(status_code=resp.status_code, detail="Unable to resolve PIDP users")
        pidp_users = resp.json() if isinstance(resp.json(), list) else []
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to load PIDP users for admin list: {exc}")
        raise HTTPException(status_code=503, detail="Unable to load admin list")

    admin_emails: set[str] = set()
    for pidp_user in pidp_users:
        pidp_id = str(pidp_user.get("id") or "").strip()
        email = str(pidp_user.get("email") or "").strip().lower()
        if not pidp_id or not email:
            continue
        is_admin = pidp_id in ORG_ADMIN_USER_IDS or await _spicedb_check_admin(pidp_id)
        if is_admin:
            admin_emails.add(email)

    if not admin_emails:
        return []

    admins = (
        session.query(Account)
        .filter(func.lower(Account.email).in_(admin_emails))
        .order_by(Account.balance.desc(), Account.name.asc())
        .all()
    )
    return admins

@app.patch("/api/accounts/me", response_model=AccountResponse)
async def update_account(
    update_data: AccountUpdate,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Update current user's account information"""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Create edit request for verification (for sensitive fields)
    edit_request = EditRequest(
        id=uuid.uuid4(),
        account_id=account.id,
        field_name="account_update",
        old_value=json.dumps({
            "name": account.name,
            "address": account.address,
            "business_type": account.business_type,
            "mission_statement": account.mission_statement
        }),
        new_value=json.dumps(update_data.dict(exclude_unset=True)),
        status="pending",
        message="Account information update request"
    )
    session.add(edit_request)
    
    # Update immediately for non-sensitive fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(account, field, value)
    
    account.updated_at = datetime.now(timezone.utc)
    
    session.commit()
    session.refresh(account)
    
    return account

# ============= TRANSACTION ENDPOINTS =============

@app.post("/api/transactions", response_model=TransactionResponse)
async def create_transaction(
    transaction_data: TransactionCreate,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db),
    conn: asyncpg.Connection = Depends(get_async_db)
):
    """Create a new financial transaction"""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Get sender account
    sender = session.query(Account).filter_by(email=current_user["email"]).first()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender account not found")
    
    # Check if recipient exists (if specified)
    recipient = None
    if transaction_data.to_account_id:
        recipient = session.query(Account).filter_by(id=transaction_data.to_account_id).first()
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient account not found")
    
    # Public transaction creation must not allow callers to mint funds via
    # system-issued transaction types. Those flows are handled by dedicated
    # server-side routines that do not debit a user account.
    privileged_types = {TransactionType.UBI_PAYMENT, TransactionType.GRANT}
    if transaction_data.transaction_type in privileged_types:
        raise HTTPException(status_code=403, detail="Transaction type is not allowed")

    # Check balance for outgoing transactions
    if sender.balance < transaction_data.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")
    
    # Use database transaction with asyncpg for better concurrency
    transaction_id = uuid.uuid4()
    
    try:
        # Update balances atomically. asyncpg returns strings like "UPDATE 1";
        # require the conditional debit to affect one row before crediting any
        # recipient so concurrent requests cannot overdraw and over-credit.
        debit_result = await conn.execute("""
            UPDATE accounts
            SET balance = balance - $1, updated_at = NOW()
            WHERE id = $2 AND balance >= $1
        """, float(transaction_data.amount), sender.id)
        if debit_result != "UPDATE 1":
            raise HTTPException(status_code=400, detail="Insufficient funds")
        
        if recipient:
            await conn.execute("""
                UPDATE accounts 
                SET balance = balance + $1, updated_at = NOW()
                WHERE id = $2
            """, float(transaction_data.amount), recipient.id)
        
        # Create transaction record
        transaction = Transaction(
            id=transaction_id,
            from_account_id=sender.id,
            to_account_id=recipient.id if recipient else None,
            amount=transaction_data.amount,
            transaction_type=transaction_data.transaction_type,
            description=transaction_data.description,
            reference_id=transaction_data.reference_id,
            tx_metadata=transaction_data.metadata
        )
        
        session.add(transaction)
        session.commit()
        session.refresh(transaction)
        
        # Cache transaction in Redis for quick access
        cache_key = f"transaction:{transaction_id}"
        db.redis_client.setex(
            cache_key,
            300,  # 5 minutes
            json.dumps({
                "id": str(transaction.id),
                "from_account_id": str(transaction.from_account_id) if transaction.from_account_id else None,
                "to_account_id": str(transaction.to_account_id) if transaction.to_account_id else None,
                "amount": str(transaction.amount),
                "transaction_type": transaction.transaction_type.value,
                "description": transaction.description,
                "timestamp": transaction.timestamp.isoformat(),
                "metadata": transaction.tx_metadata,
            })
        )
        
        return transaction
        
    except asyncpg.exceptions.CheckViolationError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Transaction failed: constraint violation")
    except Exception as e:
        session.rollback()
        logger.error(f"Transaction failed: {e}")
        raise HTTPException(status_code=500, detail="Transaction failed")

@app.get("/api/accounts/me/transactions", response_model=List[TransactionResponse])
async def get_my_transactions(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50
):
    """Get current user's transaction history"""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    transactions = session.query(Transaction).filter(
        (Transaction.from_account_id == account.id) | 
        (Transaction.to_account_id == account.id)
    ).order_by(Transaction.timestamp.desc()).offset(skip).limit(limit).all()
    
    return transactions

@app.get("/api/accounts/me/transactions/incoming", response_model=List[TransactionResponse])
async def get_my_incoming_transactions(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db),
    since: Optional[datetime] = None,
    limit: int = 50,
):
    """Get incoming transactions only for current user, suitable for polling automation."""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")

    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    safe_limit = max(1, min(limit, 500))
    query = session.query(Transaction).filter(Transaction.to_account_id == account.id)
    if since is not None:
        query = query.filter(Transaction.timestamp >= since)
    return query.order_by(Transaction.timestamp.desc()).limit(safe_limit).all()

@app.get("/api/transactions/recent", response_model=List[RecentTransactionResponse])
async def get_recent_transactions(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db),
    limit: int = 10,
):
    """Get most recent transactions across the org ledger."""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")

    safe_limit = max(1, min(limit, 100))
    txns = (
        session.query(Transaction)
        .order_by(Transaction.timestamp.desc())
        .limit(safe_limit)
        .all()
    )
    if not txns:
        return []

    account_ids: set[uuid.UUID] = set()
    for txn in txns:
        if txn.from_account_id:
            account_ids.add(txn.from_account_id)
        if txn.to_account_id:
            account_ids.add(txn.to_account_id)

    account_name_map: dict[uuid.UUID, str] = {}
    if account_ids:
        rows = session.query(Account.id, Account.name).filter(Account.id.in_(account_ids)).all()
        account_name_map = {row.id: row.name for row in rows}

    return [
        {
            "id": txn.id,
            "timestamp": txn.timestamp,
            "transaction_type": txn.transaction_type,
            "amount": txn.amount,
            "currency": txn.currency,
            "description": txn.description,
            "from_account_id": txn.from_account_id,
            "to_account_id": txn.to_account_id,
            "from_account_name": account_name_map.get(txn.from_account_id) if txn.from_account_id else None,
            "to_account_name": account_name_map.get(txn.to_account_id) if txn.to_account_id else None,
        }
        for txn in txns
    ]

# ============= UBI ENDPOINTS =============

@app.get("/api/ubi/eligibility")
async def get_ubi_eligibility(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Check UBI eligibility and next payment"""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    eligibility = session.query(UBIEligibility).filter_by(account_id=account.id).first()
    
    if not eligibility:
        return {
            "is_eligible": False,
            "reason": "Not enrolled in UBI system"
        }
    
    # Check if payment is due
    if date.today() >= eligibility.next_payment_date:
        # Calculate UBI amount based on system metrics
        system_metrics = await get_system_metrics()
        ubi_amount = EconomicEngine.calculate_ubi_amount(
            account.balance,
            system_metrics["average_balance"]
        )
        
        # Process payment in background
        asyncio.create_task(process_ubi_payment(account.id, ubi_amount))
        
        return {
            "is_eligible": True,
            "payment_due": True,
            "estimated_amount": ubi_amount,
            "next_payment_date": eligibility.next_payment_date
        }
    
    return {
        "is_eligible": eligibility.is_eligible,
        "payment_due": False,
        "next_payment_date": eligibility.next_payment_date,
        "last_payment_amount": eligibility.last_payment_amount,
        "total_payments_received": eligibility.total_payments_received
    }

@app.get("/api/ubi/settings", response_model=UBIRuntimeSettingsResponse)
async def get_ubi_settings(
    current_user: dict = Depends(get_current_user),
):
    """Read runtime UBI settings used by the UBI worker."""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return await get_ubi_runtime_settings()

@app.patch("/api/ubi/settings", response_model=UBIRuntimeSettingsResponse)
async def update_ubi_settings(
    payload: UBIRuntimeSettingsUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update runtime UBI settings used by the UBI worker."""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    updates = payload.dict(exclude_unset=True)
    if not updates:
        return await get_ubi_runtime_settings()

    interval_seconds = updates.get("interval_seconds")
    dena_annual = updates.get("dena_annual")
    dena_precision = updates.get("dena_precision")
    entity_types = updates.get("entity_types")
    entity_types_csv = ",".join(entity_types) if entity_types is not None else None

    try:
        await ensure_ubi_runtime_settings_table()
        async with db.async_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ubi_runtime_settings
                SET interval_seconds = COALESCE($1, interval_seconds),
                    dena_annual = COALESCE($2, dena_annual),
                    dena_precision = COALESCE($3, dena_precision),
                    entity_types = COALESCE($4, entity_types),
                    updated_at = NOW(),
                    updated_by = $5
                WHERE id = 1
                """,
                interval_seconds,
                float(dena_annual) if dena_annual is not None else None,
                dena_precision,
                entity_types_csv,
                current_user.get("email"),
            )
    except Exception as exc:
        logger.error(f"Failed to update UBI settings: {exc}")
        raise HTTPException(status_code=503, detail="UBI settings service temporarily unavailable")
    return await get_ubi_runtime_settings()

async def process_ubi_payment(account_id: uuid.UUID, amount: Decimal):
    """Process UBI payment asynchronously"""
    async with db.async_pool.acquire() as conn:
        try:
            async with conn.transaction():
                # Update account balance
                await conn.execute("""
                    UPDATE accounts 
                    SET balance = balance + $1, updated_at = NOW()
                    WHERE id = $2
                """, float(amount), account_id)
                
                # Create transaction
                transaction_id = uuid.uuid4()
                await conn.execute("""
                    INSERT INTO transactions 
                    (id, to_account_id, amount, transaction_type, description, timestamp)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                """, transaction_id, account_id, float(amount), 
                   TransactionType.UBI_PAYMENT.value, "Universal Basic Income payment")
                
                # Update UBI eligibility
                next_payment = date.today() + timedelta(days=UBI_PAYMENT_CYCLE)
                await conn.execute("""
                    UPDATE ubi_eligibility 
                    SET last_payment_date = $1, 
                        last_payment_amount = $2,
                        next_payment_date = $3,
                        total_payments_received = total_payments_received + $2,
                        updated_at = NOW()
                    WHERE account_id = $4
                """, date.today(), float(amount), next_payment, account_id)
                
                logger.info(f"Processed UBI payment of {amount} to account {account_id}")
                
        except Exception as e:
            logger.error(f"Failed to process UBI payment: {e}")

def calculate_ubi_amount(
    account_balance: Decimal,
    system_average_balance: Decimal
) -> Decimal:
    """Calculate UBI amount with means testing"""
    base_amount = INITIAL_UBI_AMOUNT
    
    # Adjust based on relative wealth
    if account_balance < system_average_balance * Decimal('0.5'):
        # Boost for poorer individuals
        base_amount *= Decimal('1.3')
    elif account_balance > system_average_balance * Decimal('2.0'):
        # Reduce for wealthier individuals
        base_amount *= Decimal('0.7')
    
    return base_amount.quantize(Decimal('0.01'), rounding=ROUND_DOWN)

# ============= STOCK MARKET ENDPOINTS =============

@app.post("/api/stocks", response_model=dict)
async def create_stock(
    stock_data: StockCreate,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Create a new publicly traded company (admin/business only)"""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Check if business is verified
    if not current_user.get("is_admin") and (account.entity_type != EntityType.BUSINESS or not account.is_verified):
        raise HTTPException(status_code=403, detail="Only verified businesses can issue stocks")
    
    # Check if ticker symbol already exists
    existing = session.query(Stock).filter_by(ticker_symbol=stock_data.ticker_symbol).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ticker symbol already exists")
    
    # Create stock
    stock = Stock(
        id=uuid.uuid4(),
        company_name=stock_data.company_name,
        ticker_symbol=stock_data.ticker_symbol,
        current_price=stock_data.initial_price,
        day_open=stock_data.initial_price,
        day_high=stock_data.initial_price,
        day_low=stock_data.initial_price,
        total_shares=stock_data.total_shares,
        shares_outstanding=stock_data.total_shares,
        market_cap=stock_data.initial_price * stock_data.total_shares,
        sector=stock_data.sector,
        description=stock_data.description
    )
    
    session.add(stock)
    session.commit()
    
    # Reserve shares for the company
    holding = PortfolioHolding(
        id=uuid.uuid4(),
        account_id=account.id,
        stock_id=stock.id,
        quantity=stock_data.total_shares,
        average_purchase_price=stock_data.initial_price,
        total_invested=stock_data.initial_price * stock_data.total_shares
    )
    
    session.add(holding)
    session.commit()
    
    return {"stock_id": stock.id, "message": "Stock created successfully"}

@app.get("/api/stocks", response_model=List[dict])
async def list_stocks(
    session: Session = Depends(get_db),
    sector: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
):
    """List all available stocks"""
    query = session.query(Stock).filter_by(is_active=True)
    
    if sector:
        query = query.filter_by(sector=sector)
    
    stocks = query.order_by(Stock.market_cap.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": stock.id,
            "company_name": stock.company_name,
            "ticker_symbol": stock.ticker_symbol,
            "current_price": stock.current_price,
            "day_change": ((stock.current_price - stock.day_open) / stock.day_open * 100) if stock.day_open > 0 else 0,
            "volume": stock.volume,
            "market_cap": stock.market_cap,
            "sector": stock.sector
        }
        for stock in stocks
    ]

@app.post("/api/stocks/orders")
async def place_stock_order(
    order_data: StockOrderCreate,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db),
    conn: asyncpg.Connection = Depends(get_async_db)
):
    """Place a stock market order"""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check market hours
    if not is_market_open():
        raise HTTPException(status_code=400, detail="Market is closed")
    
    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    stock = session.query(Stock).filter_by(id=order_data.stock_id).first()
    if not stock or not stock.is_active:
        raise HTTPException(status_code=404, detail="Stock not found or inactive")
    
    # Calculate order price
    order_price = order_data.limit_price if order_data.order_type == OrderType.LIMIT else stock.current_price
    total_cost = order_price * order_data.quantity if order_data.action == "buy" else Decimal('0.00')
    
    try:
        # Use database transaction for order placement
        async with conn.transaction():
            if order_data.action == "buy":
                # Check balance
                if account.balance < total_cost:
                    raise HTTPException(status_code=400, detail="Insufficient funds")
                
                # Reserve funds
                await conn.execute("""
                    UPDATE accounts 
                    SET balance = balance - $1, updated_at = NOW()
                    WHERE id = $2 AND balance >= $1
                """, float(total_cost), account.id)
                
            else:  # sell
                # Check holdings
                holding = await conn.fetchrow("""
                    SELECT quantity FROM portfolio_holdings 
                    WHERE account_id = $1 AND stock_id = $2
                """, account.id, stock.id)
                
                if not holding or holding['quantity'] < order_data.quantity:
                    raise HTTPException(status_code=400, detail="Insufficient shares")
            
            # Create order
            order_id = uuid.uuid4()
            await conn.execute("""
                INSERT INTO stock_orders 
                (id, account_id, stock_id, order_type, action, quantity, limit_price, status, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            """, order_id, account.id, stock.id, order_data.order_type.value, 
               order_data.action, order_data.quantity, 
               float(order_data.limit_price) if order_data.limit_price else None,
               OrderStatus.PENDING.value)
            
            # Try to match order immediately (simplified)
            await match_order(conn, order_id, stock, order_price, order_data.action)
            
            return {"order_id": order_id, "status": "placed"}
            
    except asyncpg.exceptions.CheckViolationError:
        raise HTTPException(status_code=400, detail="Order placement failed")
    except Exception as e:
        logger.error(f"Order placement failed: {e}")
        raise HTTPException(status_code=500, detail="Order placement failed")

async def match_order(
    conn: asyncpg.Connection,
    order_id: uuid.UUID,
    stock: Stock,
    price: Decimal,
    action: str
):
    """Match stock orders (simplified implementation)"""
    # In a real system, this would match against opposite orders
    # For now, execute immediately at current price
    
    await conn.execute("""
        UPDATE stock_orders 
        SET status = $1, executed_price = $2, executed_quantity = quantity, executed_at = NOW()
        WHERE id = $3
    """, OrderStatus.EXECUTED.value, float(stock.current_price), order_id)
    
    # Update stock price based on order
    price_impact = Decimal('0.001') * Decimal(stock.volume / max(stock.total_shares, 1))
    if action == "buy":
        new_price = stock.current_price * (Decimal('1.0') + price_impact)
    else:
        new_price = stock.current_price * (Decimal('1.0') - price_impact)
    
    await conn.execute("""
        UPDATE stocks 
        SET current_price = $1, 
            day_high = GREATEST(day_high, $1),
            day_low = LEAST(day_low, $1),
            volume = volume + 1,
            last_updated = NOW()
        WHERE id = $2
    """, float(new_price), stock.id)

# ============= PORTFOLIO ENDPOINTS =============

@app.get("/api/portfolio", response_model=dict)
async def get_portfolio(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Get user's investment portfolio"""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Get holdings with current prices
    holdings = session.query(
        PortfolioHolding, Stock
    ).join(
        Stock, PortfolioHolding.stock_id == Stock.id
    ).filter(
        PortfolioHolding.account_id == account.id,
        PortfolioHolding.quantity > 0
    ).all()
    
    portfolio_value = Decimal('0.00')
    total_invested = Decimal('0.00')
    holdings_data = []
    
    for holding, stock in holdings:
        current_value = stock.current_price * holding.quantity
        portfolio_value += current_value
        total_invested += holding.total_invested or Decimal('0.00')
        
        holdings_data.append({
            "stock_id": stock.id,
            "ticker_symbol": stock.ticker_symbol,
            "company_name": stock.company_name,
            "quantity": holding.quantity,
            "average_price": holding.average_purchase_price,
            "current_price": stock.current_price,
            "current_value": current_value,
            "unrealized_gain": current_value - (holding.total_invested or Decimal('0.00'))
        })
    
    return {
        "account_id": account.id,
        "portfolio_value": portfolio_value,
        "total_invested": total_invested,
        "unrealized_gains": portfolio_value - total_invested,
        "holdings": holdings_data,
        "cash_balance": account.balance
    }

# ============= INSURANCE ENDPOINTS =============

@app.get("/api/insurance/policies", response_model=List[dict])
async def list_insurance_policies(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """List insurance policies for the current account"""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")

    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    policies = (
        session.query(InsurancePolicy)
        .filter_by(account_id=account.id)
        .order_by(InsurancePolicy.start_date.desc())
        .all()
    )

    return [
        {
            "id": policy.id,
            "insurance_type": policy.insurance_type.value,
            "coverage_amount": policy.coverage_amount,
            "premium_amount": policy.premium_amount,
            "duration_years": policy.duration_years,
            "start_date": policy.start_date,
            "end_date": policy.end_date,
            "deductible": policy.deductible,
            "is_active": policy.is_active,
        }
        for policy in policies
    ]

@app.post("/api/insurance/policies", response_model=dict)
async def create_insurance_policy(
    policy_data: InsurancePolicyCreate,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Purchase an insurance policy"""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Calculate premium (simplified - would use actual risk assessment)
    risk_factors = {"age": 35, "health_score": 75, "location_risk": "medium"}
    premium = EconomicEngine.calculate_insurance_premium(
        policy_data.insurance_type,
        policy_data.coverage_amount,
        risk_factors
    )
    
    # Check balance
    if account.balance < premium:
        raise HTTPException(status_code=400, detail="Insufficient funds for premium")
    
    # Create policy
    policy = InsurancePolicy(
        id=uuid.uuid4(),
        account_id=account.id,
        insurance_type=policy_data.insurance_type,
        coverage_amount=policy_data.coverage_amount,
        premium_amount=premium,
        duration_years=policy_data.duration_years,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=policy_data.duration_years * 365),
        beneficiaries=policy_data.beneficiaries,
        deductible=policy_data.deductible
    )
    
    # Deduct premium
    account.balance -= premium
    
    # Record transaction
    transaction = Transaction(
        id=uuid.uuid4(),
        from_account_id=account.id,
        amount=premium,
        transaction_type=TransactionType.INSURANCE_PREMIUM,
        description=f"{policy_data.insurance_type.value} insurance premium"
    )
    
    session.add(policy)
    session.add(transaction)
    session.commit()
    
    return {
        "policy_id": policy.id,
        "premium": premium,
        "coverage_amount": policy_data.coverage_amount,
        "start_date": policy.start_date,
        "end_date": policy.end_date
    }

# ============= FISCAL POLICY ENDPOINTS =============

@app.post("/api/fiscal/proposals", response_model=dict)
async def create_fiscal_proposal(
    proposal_data: FiscalProposalCreate,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Create a new fiscal policy proposal"""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Check if user can create proposals (e.g., verified account)
    if not account.is_verified and account.entity_type == EntityType.INDIVIDUAL:
        raise HTTPException(status_code=403, detail="Account must be verified to create proposals")
    
    # Create proposal
    proposal = FiscalProposal(
        id=uuid.uuid4(),
        title=proposal_data.title,
        description=proposal_data.description,
        policy_area=proposal_data.policy_area,
        proposed_budget=proposal_data.proposed_budget,
        duration_months=proposal_data.duration_months,
        expected_impact=proposal_data.expected_impact,
        created_by=account.id,
        voting_start=datetime.now(timezone.utc),
        voting_end=datetime.now(timezone.utc) + timedelta(days=proposal_data.voting_days),
        status="voting"
    )
    
    session.add(proposal)
    session.commit()
    
    # Cache in Redis for quick access
    cache_key = f"proposal:{proposal.id}"
    db.redis_client.setex(
        cache_key,
        3600,  # 1 hour
        json.dumps({
            "id": str(proposal.id),
            "title": proposal.title,
            "policy_area": proposal.policy_area.value,
            "proposed_budget": str(proposal.proposed_budget),
            "status": proposal.status,
            "voting_end": proposal.voting_end.isoformat()
        })
    )
    
    return {"proposal_id": proposal.id, "status": "created"}

@app.post("/api/fiscal/proposals/{proposal_id}/vote")
async def vote_on_proposal(
    proposal_id: uuid.UUID,
    vote_data: FiscalVoteCreate,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db),
    conn: asyncpg.Connection = Depends(get_async_db)
):
    """Vote on a fiscal proposal"""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    proposal = session.query(FiscalProposal).filter_by(id=proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    # Check if voting is still open
    if proposal.status != "voting" or datetime.now(timezone.utc) > proposal.voting_end:
        raise HTTPException(status_code=400, detail="Voting is closed")
    
    # Check if already voted
    existing_vote = session.query(FiscalVote).filter_by(
        proposal_id=proposal_id,
        account_id=account.id
    ).first()
    
    if existing_vote:
        raise HTTPException(status_code=400, detail="Already voted on this proposal")
    
    try:
        # Use database transaction for atomic vote
        async with conn.transaction():
            # Create vote
            await conn.execute("""
                INSERT INTO fiscal_votes (id, proposal_id, account_id, vote, rationale, timestamp)
                VALUES ($1, $2, $3, $4, $5, NOW())
            """, uuid.uuid4(), proposal_id, account.id, vote_data.vote.value, vote_data.rationale)
            
            # Update proposal vote counts atomically
            await conn.execute(f"""
                UPDATE fiscal_proposals 
                SET {vote_data.vote.value}_votes = {vote_data.vote.value}_votes + 1,
                    total_votes = total_votes + 1,
                    updated_at = NOW()
                WHERE id = $1
            """, proposal_id)
        
        return {"status": "vote_recorded", "vote": vote_data.vote}
        
    except Exception as e:
        logger.error(f"Vote failed: {e}")
        raise HTTPException(status_code=500, detail="Vote failed")

# ============= TAX ENDPOINTS =============

@app.post("/api/tax/calculate")
async def calculate_tax(
    tax_data: TaxEstimate,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Calculate estimated tax liability"""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    tax_amount = EconomicEngine.calculate_tax(tax_data.taxable_income, account.entity_type)
    
    # Check for existing tax record
    existing = session.query(TaxRecord).filter_by(
        account_id=account.id,
        tax_year=tax_data.tax_year
    ).first()
    
    if existing:
        return {
            "taxable_income": tax_data.taxable_income,
            "tax_amount": tax_amount,
            "already_paid": existing.paid_amount,
            "balance_due": tax_amount - existing.paid_amount,
            "due_date": existing.due_date
        }
    
    # Create tax record if doesn't exist
    tax_record = TaxRecord(
        id=uuid.uuid4(),
        account_id=account.id,
        tax_year=tax_data.tax_year,
        taxable_income=tax_data.taxable_income,
        tax_amount=tax_amount,
        due_date=date(tax_data.tax_year + 1, 4, 15)  # Tax day in US
    )
    
    session.add(tax_record)
    session.commit()
    
    return {
        "taxable_income": tax_data.taxable_income,
        "tax_amount": tax_amount,
        "due_date": tax_record.due_date,
        "record_id": tax_record.id
    }

@app.post("/api/tax/pay")
async def pay_taxes(
    record_id: uuid.UUID,
    amount: Decimal,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db),
    conn: asyncpg.Connection = Depends(get_async_db)
):
    """Pay taxes"""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    account = session.query(Account).filter_by(email=current_user["email"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    tax_record = session.query(TaxRecord).filter_by(id=record_id, account_id=account.id).first()
    if not tax_record:
        raise HTTPException(status_code=404, detail="Tax record not found")
    
    if amount <= Decimal('0.00'):
        raise HTTPException(status_code=400, detail="Payment amount must be positive")
    
    if amount > tax_record.tax_amount - tax_record.paid_amount:
        raise HTTPException(status_code=400, detail="Payment exceeds tax due")
    
    if account.balance < amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")
    
    try:
        async with conn.transaction():
            # Deduct from account
            await conn.execute("""
                UPDATE accounts 
                SET balance = balance - $1, updated_at = NOW()
                WHERE id = $2 AND balance >= $1
            """, float(amount), account.id)
            
            # Update tax record
            await conn.execute("""
                UPDATE tax_records 
                SET paid_amount = paid_amount + $1,
                    status = CASE 
                        WHEN paid_amount + $1 >= tax_amount THEN 'paid'
                        ELSE 'partial'
                    END,
                    paid_at = CASE 
                        WHEN paid_amount + $1 >= tax_amount THEN NOW()
                        ELSE paid_at
                    END,
                    updated_at = NOW()
                WHERE id = $2
            """, float(amount), record_id)
            
            # Record transaction
            await conn.execute("""
                INSERT INTO transactions 
                (id, from_account_id, amount, transaction_type, description, timestamp)
                VALUES ($1, $2, $3, $4, $5, NOW())
            """, uuid.uuid4(), account.id, float(amount), 
               TransactionType.TAX_PAYMENT.value, f"Tax payment for {tax_record.tax_year}")
        
        return {"paid": amount, "remaining": tax_record.tax_amount - tax_record.paid_amount - amount}
        
    except Exception as e:
        logger.error(f"Tax payment failed: {e}")
        raise HTTPException(status_code=500, detail="Tax payment failed")

# ============= SYSTEM METRICS =============

async def get_system_metrics():
    """Get comprehensive system metrics"""
    async with db.async_pool.acquire() as conn:
        # Try to get from cache first
        cache_key = "system_metrics"
        cached = db.redis_client.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        # Calculate metrics
        metrics = {}
        
        # Account statistics
        result = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_accounts,
                AVG(balance) as average_balance,
                SUM(balance) as total_money_supply,
                COUNT(CASE WHEN LOWER(entity_type::text) = 'individual' THEN 1 END) as individual_accounts,
                COUNT(CASE WHEN LOWER(entity_type::text) = 'business' THEN 1 END) as business_accounts,
                COUNT(CASE WHEN LOWER(entity_type::text) = 'nonprofit' THEN 1 END) as nonprofit_accounts
            FROM accounts
        """)
        
        metrics.update(dict(result))
        
        # Transaction statistics
        result = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_transactions,
                SUM(amount) as total_transaction_volume,
                COUNT(CASE WHEN LOWER(transaction_type::text) = 'ubi_payment' THEN 1 END) as ubi_payments,
                COUNT(CASE WHEN LOWER(transaction_type::text) = 'tax_payment' THEN 1 END) as tax_payments
            FROM transactions
            WHERE timestamp > NOW() - INTERVAL '30 days'
        """)
        
        metrics.update(dict(result))
        
        # Market statistics
        result = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_stocks,
                SUM(market_cap) as total_market_cap,
                AVG(current_price) as average_stock_price
            FROM stocks
            WHERE is_active = true
        """)
        
        metrics.update(dict(result))
        
        # Normalize DB numerics (e.g., Decimal) for cache/storage compatibility.
        encoded_metrics = jsonable_encoder(metrics)

        # Cache for 5 minutes
        db.redis_client.setex(cache_key, 300, json.dumps(encoded_metrics))
        
        return encoded_metrics

@app.get("/api/system/metrics")
async def get_system_metrics_endpoint():
    """Get system-wide economic metrics"""
    metrics = await get_system_metrics()
    
    # Add real-time data
    metrics["timestamp"] = datetime.now(timezone.utc).isoformat()
    metrics["market_open"] = is_market_open()
    metrics["currency"] = SYSTEM_CURRENCY
    
    return metrics

@app.get("/api/system/money-supply/history", response_model=MoneySupplyHistoryResponse)
async def get_money_supply_history(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db),
    days: int = 365,
    bucket: str = "day",
):
    """Get total Dena in circulation as a time series."""
    if current_user.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Authentication required")

    safe_days = max(1, min(days, 3650))
    if bucket not in {"hour", "day", "week"}:
        raise HTTPException(status_code=400, detail="bucket must be one of: hour, day, week")
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=safe_days)

    def floor_bucket(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        if bucket == "hour":
            return dt.replace(minute=0, second=0, microsecond=0)
        if bucket == "week":
            monday = dt - timedelta(days=dt.weekday())
            return monday.replace(hour=0, minute=0, second=0, microsecond=0)
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    step = timedelta(hours=1) if bucket == "hour" else timedelta(days=7) if bucket == "week" else timedelta(days=1)

    current_total_supply = Decimal("0")
    tx_rows: list[tuple[datetime, Any, Any, Decimal]] = []
    try:
        current_total_supply = Decimal(
            str(session.query(func.coalesce(func.sum(Account.balance), 0)).scalar() or 0)
        )
        tx_rows = (
            session.query(Transaction.timestamp, Transaction.from_account_id, Transaction.to_account_id, Transaction.amount)
            .filter(Transaction.timestamp >= start_time)
            .order_by(Transaction.timestamp.asc())
            .all()
        )
    except Exception as exc:
        logger.error(f"Money supply history query failed, serving fallback series: {exc}")

    delta_by_bucket: dict[datetime, Decimal] = {}
    for timestamp, from_account_id, to_account_id, amount in tx_rows:
        b = floor_bucket(timestamp)
        delta = Decimal("0")
        if from_account_id is None and to_account_id is not None:
            delta = Decimal(str(amount or 0))
        elif from_account_id is not None and to_account_id is None:
            delta = -Decimal(str(amount or 0))
        if delta:
            delta_by_bucket[b] = delta_by_bucket.get(b, Decimal("0")) + delta

    start_bucket = floor_bucket(start_time)
    end_bucket = floor_bucket(now)
    buckets: list[datetime] = []
    cursor = start_bucket
    while cursor <= end_bucket:
        buckets.append(cursor)
        cursor += step

    window_delta = sum((delta_by_bucket.get(b, Decimal("0")) for b in buckets), Decimal("0"))
    running_total = current_total_supply - window_delta

    points: list[dict[str, Any]] = []
    for b in buckets:
        running_total += delta_by_bucket.get(b, Decimal("0"))
        points.append(
            {
                "timestamp": b,
                "total_supply": running_total,
            }
        )

    return {
        "points": points,
        "current_total_supply": current_total_supply,
        "currency": SYSTEM_CURRENCY,
    }

# ============= UTILITY FUNCTIONS =============

def is_market_open() -> bool:
    """Check if stock market is open"""
    now = datetime.now(timezone.utc)
    
    # Check if it's a weekend
    if now.weekday() >= 5:
        return False
    
    # Check time (9 AM to 5 PM UTC)
    market_open = now.replace(hour=STOCK_MARKET_OPEN_HOUR, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=STOCK_MARKET_CLOSE_HOUR, minute=0, second=0, microsecond=0)
    
    return market_open <= now <= market_close

# ============= BACKGROUND TASKS =============

async def update_stock_prices():
    """Background task to update stock prices"""
    while True:
        if is_market_open():
            async with db.async_pool.acquire() as conn:
                try:
                    # Get all active stocks
                    stocks = await conn.fetch("SELECT * FROM stocks WHERE is_active = true")
                    
                    for stock in stocks:
                        # Calculate price variation
                        market_sentiment = Decimal(str(random.uniform(0.4, 0.6)))  # Simulated sentiment
                        new_price = EconomicEngine.calculate_stock_price_variation(
                            Decimal(str(stock['current_price'])),
                            stock['volume'],
                            market_sentiment
                        )
                        
                        # Update stock price
                        await conn.execute("""
                            UPDATE stocks 
                            SET current_price = $1,
                                day_high = GREATEST(day_high, $1),
                                day_low = LEAST(day_low, $1),
                                last_updated = NOW()
                            WHERE id = $2
                        """, float(new_price), stock['id'])
                    
                    logger.info(f"Updated prices for {len(stocks)} stocks")
                    
                except Exception as e:
                    logger.error(f"Failed to update stock prices: {e}")
        
        await asyncio.sleep(60)  # Update every minute

async def check_and_process_proposals():
    """Background task to check and process completed proposals"""
    while True:
        async with db.async_pool.acquire() as conn:
            try:
                # Find proposals where voting has ended
                proposals = await conn.fetch("""
                    SELECT * FROM fiscal_proposals 
                    WHERE status = 'voting' AND voting_end < NOW()
                """)
                
                for proposal in proposals:
                    # Determine if proposal passed (simple majority)
                    yes_votes = proposal['yes_votes']
                    no_votes = proposal['no_votes']
                    
                    if yes_votes > no_votes:
                        new_status = "passed"
                        # Implement budget allocation (simplified)
                        await conn.execute("""
                            INSERT INTO budget_allocations 
                            (id, fiscal_year, policy_area, allocated_amount, percentage, created_at)
                            VALUES ($1, $2, $3, $4, $5, NOW())
                            ON CONFLICT (fiscal_year, policy_area) 
                            DO UPDATE SET allocated_amount = allocated_amount + $4
                        """, uuid.uuid4(), date.today().year, proposal['policy_area'],
                           proposal['proposed_budget'], Decimal('0.0'))
                    else:
                        new_status = "rejected"
                    
                    # Update proposal status
                    await conn.execute("""
                        UPDATE fiscal_proposals 
                        SET status = $1, updated_at = NOW()
                        WHERE id = $2
                    """, new_status, proposal['id'])
                    
                    logger.info(f"Proposal {proposal['id']} {new_status}")
                    
            except Exception as e:
                logger.error(f"Failed to process proposals: {e}")
        
        await asyncio.sleep(300)  # Check every 5 minutes

# ============= STARTUP TASKS =============

@app.on_event("startup")
async def startup_tasks():
    """Start background tasks"""
    # Start stock price updates
    asyncio.create_task(update_stock_prices())
    
    # Start proposal processing
    asyncio.create_task(check_and_process_proposals())
    
    # Create sample data if needed
    await create_sample_data()

async def create_sample_data():
    """Create sample data for demonstration"""
    async with db.async_pool.acquire() as conn:
        # Check if sample data already exists
        count = await conn.fetchval("SELECT COUNT(*) FROM accounts")
        
        if count > 0:
            return
        
        logger.info("Creating sample data...")
        
        # Create sample accounts
        sample_accounts = [
            ("John Doe", "john@example.com", EntityType.INDIVIDUAL, Decimal('50000.00')),
            ("Jane Smith", "jane@example.com", EntityType.INDIVIDUAL, Decimal('75000.00')),
            ("Acme Corp", "acme@example.com", EntityType.BUSINESS, Decimal('1000000.00')),
            ("Green Energy Inc", "green@example.com", EntityType.BUSINESS, Decimal('500000.00')),
            ("Community Nonprofit", "nonprofit@example.com", EntityType.NONPROFIT, Decimal('100000.00')),
        ]
        
        for name, email, entity_type, balance in sample_accounts:
            account_id = uuid.uuid4()
            
            await conn.execute("""
                INSERT INTO accounts 
                (id, entity_type, name, email, balance, credit_score, is_verified, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, 750, true, NOW(), NOW())
            """, account_id, entity_type.value, name, email, float(balance))
            
            # Create UBI eligibility for individuals
            if entity_type == EntityType.INDIVIDUAL:
                await conn.execute("""
                    INSERT INTO ubi_eligibility 
                    (id, account_id, is_eligible, next_payment_date, created_at, updated_at)
                    VALUES ($1, $2, true, $3, NOW(), NOW())
                """, uuid.uuid4(), account_id, date.today() + timedelta(days=7))
        
        # Create sample stocks
        sample_stocks = [
            ("Democratic Energy Corp", "DEC", Decimal('50.00'), 1000000, "Energy"),
            ("People's Healthcare", "PHC", Decimal('75.00'), 500000, "Healthcare"),
            ("Sustainable Agriculture", "SAC", Decimal('30.00'), 750000, "Agriculture"),
        ]
        
        for name, ticker, price, shares, sector in sample_stocks:
            stock_id = uuid.uuid4()
            
            await conn.execute("""
                INSERT INTO stocks 
                (id, company_name, ticker_symbol, current_price, day_open, day_high, day_low,
                 volume, total_shares, shares_outstanding, market_cap, sector, is_active, created_at, last_updated)
                VALUES ($1, $2, $3, $4, $4, $4, $4, 0, $5, $5, $6, $7, true, NOW(), NOW())
            """, stock_id, name, ticker, float(price), shares, 
               float(price * shares), sector)
        
        logger.info("Sample data created successfully")

# ============= HEALTH CHECK =============

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database
        async with db.async_pool.acquire() as conn:
            await conn.execute("SELECT 1")
        
        # Check Redis
        db.redis_client.ping()
        
        return {
            "status": "healthy",
            "database": "connected",
            "redis": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Democratic Economic System API",
        "version": "2.0.0",
        "description": "A comprehensive democratic economic system with UBI, stock market, insurance, and fiscal policy",
        "documentation": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True
    )
