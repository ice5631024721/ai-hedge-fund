#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票数据模型定义

本模块定义了股票数据相关的Pydantic模型，用于规范数据结构和验证。
包括股票基本信息、历史价格数据、实时价格数据等。
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator


class TimeInterval(str, Enum):
    """时间间隔枚举"""
    ONE_MINUTE = "1m"
    TWO_MINUTES = "2m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    SIXTY_MINUTES = "60m"
    NINETY_MINUTES = "90m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    FIVE_DAYS = "5d"
    ONE_WEEK = "1wk"
    ONE_MONTH = "1mo"
    THREE_MONTHS = "3mo"


class Period(str, Enum):
    """数据周期枚举"""
    ONE_DAY = "1d"
    FIVE_DAYS = "5d"
    ONE_MONTH = "1mo"
    THREE_MONTHS = "3mo"
    SIX_MONTHS = "6mo"
    ONE_YEAR = "1y"
    TWO_YEARS = "2y"
    FIVE_YEARS = "5y"
    TEN_YEARS = "10y"
    YTD = "ytd"
    MAX = "max"


class StockInfo(BaseModel):
    """股票基本信息模型"""
    symbol: str = Field(..., description="股票代码")
    company_name: Optional[str] = Field(None, description="公司名称")
    sector: Optional[str] = Field(None, description="行业")
    industry: Optional[str] = Field(None, description="细分行业")
    market_cap: Optional[float] = Field(None, description="市值")
    currency: Optional[str] = Field(None, description="货币")
    exchange: Optional[str] = Field(None, description="交易所")
    country: Optional[str] = Field(None, description="国家")
    website: Optional[str] = Field(None, description="官网")
    description: Optional[str] = Field(None, description="公司描述")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }


class PriceData(BaseModel):
    """价格数据模型"""
    timestamp: datetime = Field(..., description="时间戳")
    open_price: Optional[float] = Field(None, description="开盘价")
    high_price: Optional[float] = Field(None, description="最高价")
    low_price: Optional[float] = Field(None, description="最低价")
    close_price: Optional[float] = Field(None, description="收盘价")
    adjusted_close: Optional[float] = Field(None, description="调整后收盘价")
    volume: Optional[int] = Field(None, description="成交量")
    
    @validator('timestamp', pre=True)
    def parse_timestamp(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RealTimePrice(BaseModel):
    """实时价格数据模型"""
    symbol: str = Field(..., description="股票代码")
    current_price: float = Field(..., description="当前价格")
    previous_close: Optional[float] = Field(None, description="前收盘价")
    change: Optional[float] = Field(None, description="价格变化")
    change_percent: Optional[float] = Field(None, description="变化百分比")
    volume: Optional[int] = Field(None, description="成交量")
    market_cap: Optional[float] = Field(None, description="市值")
    pe_ratio: Optional[float] = Field(None, description="市盈率")
    day_high: Optional[float] = Field(None, description="日内最高价")
    day_low: Optional[float] = Field(None, description="日内最低价")
    fifty_two_week_high: Optional[float] = Field(None, description="52周最高价")
    fifty_two_week_low: Optional[float] = Field(None, description="52周最低价")
    last_updated: datetime = Field(default_factory=datetime.now, description="最后更新时间")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HistoricalDataResponse(BaseModel):
    """历史数据响应模型"""
    symbol: str = Field(..., description="股票代码")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    interval: TimeInterval = Field(TimeInterval.ONE_DAY, description="时间间隔")
    price_data: List[PriceData] = Field(default_factory=list, description="价格数据列表")
    total_count: int = Field(0, description="数据总数")
    stock_info: Optional[StockInfo] = Field(None, description="股票基本信息")
    last_updated: datetime = Field(default_factory=datetime.now, description="最后更新时间")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }


class StockDataError(Exception):
    """股票数据相关异常"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self):
        return f"StockDataError({self.error_code}): {self.message}"
    
    def to_dict(self):
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }