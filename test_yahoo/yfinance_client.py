#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yfinance客户端实现

本模块实现了基于yfinance库的股票数据提供者，包括：
- YFinanceStockDataProvider: yfinance数据提供者
- MemoryCache: 内存缓存实现
- SimpleRateLimiter: 简单速率限制器
- YFinanceDataProcessor: yfinance数据处理器
"""

import time
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Union
from collections import defaultdict
import json

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    raise ImportError("请安装yfinance和pandas库: pip install yfinance pandas")

from stock_interfaces import StockDataProvider, CacheProvider, RateLimiter, DataProcessor
from stock_models import (
    StockInfo, PriceData, RealTimePrice, HistoricalDataResponse,
    TimeInterval, Period, StockDataError
)

# 配置日志
logger = logging.getLogger(__name__)


class MemoryCache(CacheProvider):
    """内存缓存实现"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key not in self._cache:
            return None
        
        cache_item = self._cache[key]
        
        # 检查是否过期
        if cache_item.get('expires_at') and datetime.now().timestamp() > cache_item['expires_at']:
            del self._cache[key]
            return None
        
        return cache_item['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值"""
        expires_at = None
        if ttl:
            expires_at = datetime.now().timestamp() + ttl
        
        self._cache[key] = {
            'value': value,
            'expires_at': expires_at,
            'created_at': datetime.now().timestamp()
        }
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()
    
    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        return self.get(key) is not None


class SimpleRateLimiter(RateLimiter):
    """简单速率限制器实现"""
    
    def __init__(self, max_requests: int = 100, time_window: int = 60):
        """
        初始化速率限制器
        
        Args:
            max_requests: 时间窗口内最大请求数
            time_window: 时间窗口（秒）
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self._requests: Dict[str, List[float]] = defaultdict(list)
    
    def can_proceed(self, identifier: str = "default") -> bool:
        """检查是否可以继续执行"""
        now = time.time()
        requests = self._requests[identifier]
        
        # 清理过期的请求记录
        self._requests[identifier] = [req_time for req_time in requests 
                                     if now - req_time < self.time_window]
        
        # 检查是否超过限制
        if len(self._requests[identifier]) >= self.max_requests:
            return False
        
        # 记录当前请求
        self._requests[identifier].append(now)
        return True
    
    def wait_time(self, identifier: str = "default") -> float:
        """获取需要等待的时间"""
        now = time.time()
        requests = self._requests[identifier]
        
        if len(requests) < self.max_requests:
            return 0.0
        
        # 计算最早请求的过期时间
        oldest_request = min(requests)
        wait_time = self.time_window - (now - oldest_request)
        return max(0.0, wait_time)
    
    def reset(self, identifier: str = "default") -> None:
        """重置速率限制"""
        if identifier in self._requests:
            del self._requests[identifier]


class YFinanceDataProcessor(DataProcessor):
    """yfinance数据处理器"""
    
    def process_historical_data(self, raw_data: Any, symbol: str) -> HistoricalDataResponse:
        """处理历史数据"""
        try:
            if raw_data is None or raw_data.empty:
                return HistoricalDataResponse(
                    symbol=symbol,
                    price_data=[],
                    total_count=0
                )
            
            price_data = []
            for timestamp, row in raw_data.iterrows():
                # 处理时间戳，支持pandas Timestamp和datetime对象
                if hasattr(timestamp, 'to_pydatetime'):
                    dt = timestamp.to_pydatetime()
                elif isinstance(timestamp, datetime):
                    dt = timestamp
                else:
                    dt = pd.to_datetime(timestamp).to_pydatetime()
                
                price_data.append(PriceData(
                    timestamp=dt,
                    open_price=float(row.get('Open', 0)) if not pd.isna(row.get('Open')) else None,
                    high_price=float(row.get('High', 0)) if not pd.isna(row.get('High')) else None,
                    low_price=float(row.get('Low', 0)) if not pd.isna(row.get('Low')) else None,
                    close_price=float(row.get('Close', 0)) if not pd.isna(row.get('Close')) else None,
                    adjusted_close=float(row.get('Adj Close', 0)) if not pd.isna(row.get('Adj Close')) else None,
                    volume=int(row.get('Volume', 0)) if not pd.isna(row.get('Volume')) else None
                ))
            
            return HistoricalDataResponse(
                symbol=symbol,
                price_data=price_data,
                total_count=len(price_data)
            )
            
        except Exception as e:
            logger.error(f"处理历史数据失败: {e}")
            raise StockDataError(f"处理历史数据失败: {str(e)}", "DATA_PROCESSING_ERROR")
    
    def process_real_time_data(self, raw_data: Any, symbol: str) -> RealTimePrice:
        """处理实时数据"""
        try:
            info = raw_data.info if hasattr(raw_data, 'info') else {}
            
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            if current_price is None:
                # 尝试从历史数据获取最新价格
                hist = raw_data.history(period="1d")
                if not hist.empty:
                    current_price = float(hist['Close'].iloc[-1])
            
            if current_price is None:
                raise StockDataError(f"无法获取{symbol}的当前价格", "PRICE_NOT_AVAILABLE")
            
            previous_close = info.get('previousClose')
            change = None
            change_percent = None
            
            if previous_close and current_price:
                change = current_price - previous_close
                change_percent = (change / previous_close) * 100
            
            return RealTimePrice(
                symbol=symbol,
                current_price=float(current_price),
                previous_close=float(previous_close) if previous_close else None,
                change=float(change) if change else None,
                change_percent=float(change_percent) if change_percent else None,
                volume=info.get('volume'),
                market_cap=info.get('marketCap'),
                pe_ratio=info.get('trailingPE'),
                day_high=info.get('dayHigh'),
                day_low=info.get('dayLow'),
                fifty_two_week_high=info.get('fiftyTwoWeekHigh'),
                fifty_two_week_low=info.get('fiftyTwoWeekLow')
            )
            
        except Exception as e:
            logger.error(f"处理实时数据失败: {e}")
            raise StockDataError(f"处理实时数据失败: {str(e)}", "DATA_PROCESSING_ERROR")
    
    def process_stock_info(self, raw_data: Any, symbol: str) -> StockInfo:
        """处理股票信息"""
        try:
            info = raw_data.info if hasattr(raw_data, 'info') else {}
            
            return StockInfo(
                symbol=symbol,
                company_name=info.get('longName') or info.get('shortName'),
                sector=info.get('sector'),
                industry=info.get('industry'),
                market_cap=info.get('marketCap'),
                currency=info.get('currency'),
                exchange=info.get('exchange'),
                country=info.get('country'),
                website=info.get('website'),
                description=info.get('longBusinessSummary')
            )
            
        except Exception as e:
            logger.error(f"处理股票信息失败: {e}")
            raise StockDataError(f"处理股票信息失败: {str(e)}", "DATA_PROCESSING_ERROR")
    
    def validate_data(self, data: Any) -> bool:
        """验证数据有效性"""
        if data is None:
            return False
        
        # 检查是否为空的DataFrame
        if hasattr(data, 'empty') and data.empty:
            return False
        
        # 检查是否有info属性（即使为空字典也认为是有效的ticker对象）
        if hasattr(data, 'info'):
            return True
        
        # 检查是否为有效的DataFrame
        if hasattr(data, 'index') and len(data.index) > 0:
            return True
        
        return False


class YFinanceStockDataProvider(StockDataProvider):
    """基于yfinance的股票数据提供者"""
    
    def __init__(self, 
                 cache: Optional[CacheProvider] = None,
                 rate_limiter: Optional[RateLimiter] = None,
                 data_processor: Optional[DataProcessor] = None,
                 cache_ttl: int = 300):
        """
        初始化yfinance数据提供者
        
        Args:
            cache: 缓存提供者
            rate_limiter: 速率限制器
            data_processor: 数据处理器
            cache_ttl: 缓存过期时间（秒）
        """
        self.cache = cache or MemoryCache()
        self.rate_limiter = rate_limiter or SimpleRateLimiter()
        self.data_processor = data_processor or YFinanceDataProcessor()
        self.cache_ttl = cache_ttl
        
        # 常见股票代码列表
        self._popular_symbols = [
            'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX',
            'BABA', 'V', 'JPM', 'JNJ', 'WMT', 'PG', 'UNH', 'HD', 'MA', 'DIS',
            'PYPL', 'BAC', 'ADBE', 'CRM', 'NFLX', 'CMCSA', 'XOM', 'VZ', 'KO',
            'PFE', 'T', 'INTC', 'ABT', 'CVX', 'PEP', 'TMO', 'COST', 'AVGO'
        ]
    
    def _wait_for_rate_limit(self) -> None:
        """等待速率限制"""
        if not self.rate_limiter.can_proceed():
            wait_time = self.rate_limiter.wait_time()
            if wait_time > 0:
                logger.info(f"速率限制，等待 {wait_time:.2f} 秒")
                time.sleep(wait_time)
    
    def _generate_cache_key(self, operation: str, **kwargs) -> str:
        """生成缓存键"""
        key_parts = [operation]
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}={v}")
        return ":".join(key_parts)
    
    def get_stock_info(self, symbol: str) -> StockInfo:
        """获取股票基本信息"""
        cache_key = self._generate_cache_key("stock_info", symbol=symbol)
        
        # 尝试从缓存获取
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return StockInfo(**cached_data)
        
        try:
            self._wait_for_rate_limit()
            
            ticker = yf.Ticker(symbol)
            
            if not self.data_processor.validate_data(ticker):
                raise StockDataError(f"无效的股票代码: {symbol}", "INVALID_SYMBOL")
            
            stock_info = self.data_processor.process_stock_info(ticker, symbol)
            
            # 缓存结果
            self.cache.set(cache_key, stock_info.dict(), self.cache_ttl)
            
            return stock_info
            
        except Exception as e:
            if isinstance(e, StockDataError):
                raise
            logger.error(f"获取股票信息失败: {e}")
            raise StockDataError(f"获取股票信息失败: {str(e)}", "API_ERROR")
    
    def get_historical_data(
        self,
        symbol: str,
        start_date: Optional[Union[str, date]] = None,
        end_date: Optional[Union[str, date]] = None,
        period: Optional[Period] = None,
        interval: TimeInterval = TimeInterval.ONE_DAY
    ) -> HistoricalDataResponse:
        """获取历史价格数据"""
        cache_key = self._generate_cache_key(
            "historical_data",
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period=period,
            interval=interval
        )
        
        # 尝试从缓存获取
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return HistoricalDataResponse(**cached_data)
        
        try:
            self._wait_for_rate_limit()
            
            ticker = yf.Ticker(symbol)
            
            # 准备参数
            kwargs = {'interval': interval.value}
            
            if period:
                kwargs['period'] = period.value
            else:
                if start_date:
                    kwargs['start'] = start_date
                if end_date:
                    kwargs['end'] = end_date
            
            # 获取历史数据
            hist_data = ticker.history(**kwargs)
            
            if not self.data_processor.validate_data(hist_data):
                raise StockDataError(f"无法获取{symbol}的历史数据", "NO_DATA")
            
            response = self.data_processor.process_historical_data(hist_data, symbol)
            
            # 添加股票信息
            try:
                response.stock_info = self.get_stock_info(symbol)
            except Exception:
                logger.warning(f"无法获取{symbol}的股票信息")
            
            # 设置日期范围
            if response.price_data:
                response.start_date = response.price_data[0].timestamp.date()
                response.end_date = response.price_data[-1].timestamp.date()
            
            response.interval = interval
            
            # 缓存结果
            self.cache.set(cache_key, response.dict(), self.cache_ttl)
            
            return response
            
        except Exception as e:
            if isinstance(e, StockDataError):
                raise
            logger.error(f"获取历史数据失败: {e}")
            raise StockDataError(f"获取历史数据失败: {str(e)}", "API_ERROR")
    
    def get_real_time_price(self, symbol: str) -> RealTimePrice:
        """获取实时价格数据"""
        cache_key = self._generate_cache_key("real_time_price", symbol=symbol)
        
        # 实时数据缓存时间较短
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return RealTimePrice(**cached_data)
        
        try:
            self._wait_for_rate_limit()
            
            ticker = yf.Ticker(symbol)
            
            if not self.data_processor.validate_data(ticker):
                raise StockDataError(f"无效的股票代码: {symbol}", "INVALID_SYMBOL")
            
            real_time_price = self.data_processor.process_real_time_data(ticker, symbol)
            
            # 缓存结果（较短时间）
            self.cache.set(cache_key, real_time_price.dict(), 60)  # 1分钟缓存
            
            return real_time_price
            
        except Exception as e:
            if isinstance(e, StockDataError):
                raise
            logger.error(f"获取实时价格失败: {e}")
            raise StockDataError(f"获取实时价格失败: {str(e)}", "API_ERROR")
    
    def validate_symbol(self, symbol: str) -> bool:
        """验证股票代码是否有效"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return bool(info and info.get('symbol'))
        except Exception:
            return False
    
    def get_supported_symbols(self) -> List[str]:
        """获取支持的股票代码列表"""
        return self._popular_symbols.copy()
    
    def search_symbols(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """搜索股票代码"""
        # 简单的本地搜索实现
        results = []
        query_lower = query.lower()
        
        for symbol in self._popular_symbols:
            if query_lower in symbol.lower():
                try:
                    info = self.get_stock_info(symbol)
                    results.append({
                        'symbol': symbol,
                        'name': info.company_name or symbol
                    })
                    if len(results) >= limit:
                        break
                except Exception:
                    continue
        
        return results


# 导入pandas用于数据处理
try:
    import pandas as pd
except ImportError:
    raise ImportError("请安装pandas库: pip install pandas")