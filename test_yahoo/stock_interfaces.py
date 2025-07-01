#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票数据接口定义

本模块定义了股票数据获取相关的抽象基类接口，用于规范不同数据源的实现。
通过抽象接口设计，可以轻松扩展新的数据源（如Alpha Vantage、Quandl等）。
"""

from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union

from stock_models import (
    StockInfo, PriceData, RealTimePrice, HistoricalDataResponse,
    TimeInterval, Period, StockDataError
)


class StockDataProvider(ABC):
    """股票数据提供者抽象基类"""
    
    @abstractmethod
    def get_stock_info(self, symbol: str) -> StockInfo:
        """
        获取股票基本信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            StockInfo: 股票基本信息
            
        Raises:
            StockDataError: 获取数据失败时抛出
        """
        pass
    
    @abstractmethod
    def get_historical_data(
        self,
        symbol: str,
        start_date: Optional[Union[str, date]] = None,
        end_date: Optional[Union[str, date]] = None,
        period: Optional[Period] = None,
        interval: TimeInterval = TimeInterval.ONE_DAY
    ) -> HistoricalDataResponse:
        """
        获取历史价格数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 数据周期（与start_date/end_date互斥）
            interval: 时间间隔
            
        Returns:
            HistoricalDataResponse: 历史数据响应
            
        Raises:
            StockDataError: 获取数据失败时抛出
        """
        pass
    
    @abstractmethod
    def get_real_time_price(self, symbol: str) -> RealTimePrice:
        """
        获取实时价格数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            RealTimePrice: 实时价格数据
            
        Raises:
            StockDataError: 获取数据失败时抛出
        """
        pass
    
    @abstractmethod
    def validate_symbol(self, symbol: str) -> bool:
        """
        验证股票代码是否有效
        
        Args:
            symbol: 股票代码
            
        Returns:
            bool: 是否有效
        """
        pass
    
    @abstractmethod
    def get_supported_symbols(self) -> List[str]:
        """
        获取支持的股票代码列表
        
        Returns:
            List[str]: 支持的股票代码列表
        """
        pass
    
    @abstractmethod
    def search_symbols(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        搜索股票代码
        
        Args:
            query: 搜索关键词
            limit: 返回结果数量限制
            
        Returns:
            List[Dict[str, str]]: 搜索结果列表，每个元素包含symbol和name
        """
        pass


class CacheProvider(ABC):
    """缓存提供者抽象基类"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            Optional[Any]: 缓存值，不存在时返回None
        """
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None表示永不过期
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        删除缓存
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否删除成功
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """
        清空所有缓存
        """
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        检查缓存是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否存在
        """
        pass


class RateLimiter(ABC):
    """速率限制器抽象基类"""
    
    @abstractmethod
    def can_proceed(self, identifier: str = "default") -> bool:
        """
        检查是否可以继续执行
        
        Args:
            identifier: 标识符，用于区分不同的限制对象
            
        Returns:
            bool: 是否可以继续执行
        """
        pass
    
    @abstractmethod
    def wait_time(self, identifier: str = "default") -> float:
        """
        获取需要等待的时间
        
        Args:
            identifier: 标识符
            
        Returns:
            float: 等待时间（秒）
        """
        pass
    
    @abstractmethod
    def reset(self, identifier: str = "default") -> None:
        """
        重置速率限制
        
        Args:
            identifier: 标识符
        """
        pass


class DataProcessor(ABC):
    """数据处理器抽象基类"""
    
    @abstractmethod
    def process_historical_data(self, raw_data: Any, symbol: str) -> HistoricalDataResponse:
        """
        处理历史数据
        
        Args:
            raw_data: 原始数据
            symbol: 股票代码
            
        Returns:
            HistoricalDataResponse: 处理后的历史数据
        """
        pass
    
    @abstractmethod
    def process_real_time_data(self, raw_data: Any, symbol: str) -> RealTimePrice:
        """
        处理实时数据
        
        Args:
            raw_data: 原始数据
            symbol: 股票代码
            
        Returns:
            RealTimePrice: 处理后的实时数据
        """
        pass
    
    @abstractmethod
    def process_stock_info(self, raw_data: Any, symbol: str) -> StockInfo:
        """
        处理股票信息
        
        Args:
            raw_data: 原始数据
            symbol: 股票代码
            
        Returns:
            StockInfo: 处理后的股票信息
        """
        pass
    
    @abstractmethod
    def validate_data(self, data: Any) -> bool:
        """
        验证数据有效性
        
        Args:
            data: 待验证的数据
            
        Returns:
            bool: 数据是否有效
        """
        pass