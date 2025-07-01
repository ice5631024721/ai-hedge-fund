#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yfinance股票数据获取程序测试用例

本模块包含对股票数据获取程序的全面测试，包括：
- 数据模型测试
- 缓存功能测试
- 速率限制器测试
- 数据处理器测试
- yfinance数据提供者测试
- 集成测试
- 性能测试
"""

import unittest
import time
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock, PropertyMock
import json

# 导入被测试的模块
from stock_models import (
    StockInfo, PriceData, RealTimePrice, HistoricalDataResponse,
    TimeInterval, Period, StockDataError
)
from stock_interfaces import StockDataProvider, CacheProvider, RateLimiter, DataProcessor
from yfinance_client import (
    MemoryCache, SimpleRateLimiter, YFinanceDataProcessor, YFinanceStockDataProvider
)


class TestStockModels(unittest.TestCase):
    """测试数据模型"""
    
    def test_stock_info_creation(self):
        """测试股票信息创建"""
        stock_info = StockInfo(
            symbol="AAPL",
            company_name="Apple Inc.",
            sector="Technology",
            market_cap=3000000000000
        )
        
        self.assertEqual(stock_info.symbol, "AAPL")
        self.assertEqual(stock_info.company_name, "Apple Inc.")
        self.assertEqual(stock_info.sector, "Technology")
        self.assertEqual(stock_info.market_cap, 3000000000000)
    
    def test_price_data_creation(self):
        """测试价格数据创建"""
        timestamp = datetime.now()
        price_data = PriceData(
            timestamp=timestamp,
            open_price=150.0,
            high_price=155.0,
            low_price=148.0,
            close_price=152.0,
            volume=1000000
        )
        
        self.assertEqual(price_data.timestamp, timestamp)
        self.assertEqual(price_data.open_price, 150.0)
        self.assertEqual(price_data.close_price, 152.0)
        self.assertEqual(price_data.volume, 1000000)
    
    def test_real_time_price_creation(self):
        """测试实时价格创建"""
        real_time = RealTimePrice(
            symbol="GOOGL",
            current_price=2800.0,
            previous_close=2750.0,
            change=50.0,
            change_percent=1.82
        )
        
        self.assertEqual(real_time.symbol, "GOOGL")
        self.assertEqual(real_time.current_price, 2800.0)
        self.assertEqual(real_time.change, 50.0)
        self.assertEqual(real_time.change_percent, 1.82)
    
    def test_historical_data_response(self):
        """测试历史数据响应"""
        price_data = [
            PriceData(
                timestamp=datetime.now(),
                open_price=100.0,
                close_price=105.0,
                volume=500000
            )
        ]
        
        response = HistoricalDataResponse(
            symbol="MSFT",
            price_data=price_data,
            total_count=1,
            interval=TimeInterval.ONE_DAY
        )
        
        self.assertEqual(response.symbol, "MSFT")
        self.assertEqual(response.total_count, 1)
        self.assertEqual(len(response.price_data), 1)
        self.assertEqual(response.interval, TimeInterval.ONE_DAY)
    
    def test_stock_data_error(self):
        """测试股票数据异常"""
        error = StockDataError(
            message="测试错误",
            error_code="TEST_ERROR",
            details={"key": "value"}
        )
        
        self.assertEqual(error.message, "测试错误")
        self.assertEqual(error.error_code, "TEST_ERROR")
        self.assertEqual(error.details["key"], "value")
        
        error_dict = error.to_dict()
        self.assertIn("error_code", error_dict)
        self.assertIn("message", error_dict)
        self.assertIn("details", error_dict)
    
    def test_json_serialization(self):
        """测试JSON序列化"""
        stock_info = StockInfo(
            symbol="TSLA",
            company_name="Tesla, Inc."
        )
        
        # 测试字典转换
        data_dict = stock_info.dict()
        self.assertIsInstance(data_dict, dict)
        self.assertEqual(data_dict["symbol"], "TSLA")
        
        # 测试JSON序列化
        json_str = json.dumps(data_dict, default=str)
        self.assertIsInstance(json_str, str)


class TestMemoryCache(unittest.TestCase):
    """测试内存缓存"""
    
    def setUp(self):
        """设置测试环境"""
        self.cache = MemoryCache()
    
    def test_set_and_get(self):
        """测试设置和获取缓存"""
        self.cache.set("test_key", "test_value")
        value = self.cache.get("test_key")
        self.assertEqual(value, "test_value")
    
    def test_get_nonexistent_key(self):
        """测试获取不存在的键"""
        value = self.cache.get("nonexistent_key")
        self.assertIsNone(value)
    
    def test_cache_expiration(self):
        """测试缓存过期"""
        self.cache.set("expire_key", "expire_value", ttl=1)
        
        # 立即获取应该成功
        value = self.cache.get("expire_key")
        self.assertEqual(value, "expire_value")
        
        # 等待过期后获取应该返回None
        time.sleep(1.1)
        value = self.cache.get("expire_key")
        self.assertIsNone(value)
    
    def test_delete(self):
        """测试删除缓存"""
        self.cache.set("delete_key", "delete_value")
        
        # 确认存在
        self.assertTrue(self.cache.exists("delete_key"))
        
        # 删除
        result = self.cache.delete("delete_key")
        self.assertTrue(result)
        
        # 确认已删除
        self.assertFalse(self.cache.exists("delete_key"))
    
    def test_clear(self):
        """测试清空缓存"""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        
        # 确认存在
        self.assertTrue(self.cache.exists("key1"))
        self.assertTrue(self.cache.exists("key2"))
        
        # 清空
        self.cache.clear()
        
        # 确认已清空
        self.assertFalse(self.cache.exists("key1"))
        self.assertFalse(self.cache.exists("key2"))
    
    def test_exists(self):
        """测试检查缓存是否存在"""
        self.assertFalse(self.cache.exists("test_exists"))
        
        self.cache.set("test_exists", "value")
        self.assertTrue(self.cache.exists("test_exists"))


class TestSimpleRateLimiter(unittest.TestCase):
    """测试简单速率限制器"""
    
    def setUp(self):
        """设置测试环境"""
        self.rate_limiter = SimpleRateLimiter(max_requests=3, time_window=2)
    
    def test_can_proceed_within_limit(self):
        """测试在限制内可以继续"""
        # 前3个请求应该成功
        for i in range(3):
            self.assertTrue(self.rate_limiter.can_proceed())
    
    def test_cannot_proceed_over_limit(self):
        """测试超过限制不能继续"""
        # 前3个请求成功
        for i in range(3):
            self.assertTrue(self.rate_limiter.can_proceed())
        
        # 第4个请求应该失败
        self.assertFalse(self.rate_limiter.can_proceed())
    
    def test_wait_time(self):
        """测试等待时间计算"""
        # 在限制内，等待时间应该为0
        self.assertEqual(self.rate_limiter.wait_time(), 0.0)
        
        # 达到限制后，等待时间应该大于0
        for i in range(3):
            self.rate_limiter.can_proceed()
        
        wait_time = self.rate_limiter.wait_time()
        self.assertGreater(wait_time, 0.0)
        self.assertLessEqual(wait_time, 2.0)
    
    def test_reset(self):
        """测试重置速率限制"""
        # 达到限制
        for i in range(3):
            self.rate_limiter.can_proceed()
        
        self.assertFalse(self.rate_limiter.can_proceed())
        
        # 重置后应该可以继续
        self.rate_limiter.reset()
        self.assertTrue(self.rate_limiter.can_proceed())
    
    def test_different_identifiers(self):
        """测试不同标识符的独立限制"""
        # 对identifier1达到限制
        for i in range(3):
            self.assertTrue(self.rate_limiter.can_proceed("id1"))
        
        self.assertFalse(self.rate_limiter.can_proceed("id1"))
        
        # identifier2应该仍然可以使用
        self.assertTrue(self.rate_limiter.can_proceed("id2"))


class TestYFinanceDataProcessor(unittest.TestCase):
    """测试yfinance数据处理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.processor = YFinanceDataProcessor()
    
    @patch('yfinance_client.pd')
    def test_process_historical_data(self, mock_pd):
        """测试处理历史数据"""
        # 模拟pandas DataFrame
        mock_df = Mock()
        mock_df.empty = False
        mock_df.iterrows.return_value = [
            (datetime(2023, 1, 1), {
                'Open': 150.0,
                'High': 155.0,
                'Low': 148.0,
                'Close': 152.0,
                'Adj Close': 151.5,
                'Volume': 1000000
            })
        ]
        
        # 模拟pd.isna
        mock_pd.isna.return_value = False
        
        response = self.processor.process_historical_data(mock_df, "AAPL")
        
        self.assertIsInstance(response, HistoricalDataResponse)
        self.assertEqual(response.symbol, "AAPL")
        self.assertEqual(response.total_count, 1)
        self.assertEqual(len(response.price_data), 1)
        
        price_data = response.price_data[0]
        self.assertEqual(price_data.open_price, 150.0)
        self.assertEqual(price_data.close_price, 152.0)
    
    def test_process_historical_data_empty(self):
        """测试处理空的历史数据"""
        mock_df = Mock()
        mock_df.empty = True
        
        response = self.processor.process_historical_data(mock_df, "AAPL")
        
        self.assertEqual(response.symbol, "AAPL")
        self.assertEqual(response.total_count, 0)
        self.assertEqual(len(response.price_data), 0)
    
    def test_process_real_time_data(self):
        """测试处理实时数据"""
        mock_ticker = Mock()
        mock_ticker.info = {
            'currentPrice': 150.0,
            'previousClose': 148.0,
            'volume': 1000000,
            'marketCap': 3000000000000,
            'trailingPE': 25.5,
            'dayHigh': 152.0,
            'dayLow': 147.0,
            'fiftyTwoWeekHigh': 180.0,
            'fiftyTwoWeekLow': 120.0
        }
        
        real_time = self.processor.process_real_time_data(mock_ticker, "AAPL")
        
        self.assertIsInstance(real_time, RealTimePrice)
        self.assertEqual(real_time.symbol, "AAPL")
        self.assertEqual(real_time.current_price, 150.0)
        self.assertEqual(real_time.previous_close, 148.0)
        self.assertEqual(real_time.change, 2.0)
        self.assertAlmostEqual(real_time.change_percent, 1.35, places=2)
    
    def test_process_stock_info(self):
        """测试处理股票信息"""
        mock_ticker = Mock()
        mock_ticker.info = {
            'longName': 'Apple Inc.',
            'sector': 'Technology',
            'industry': 'Consumer Electronics',
            'marketCap': 3000000000000,
            'currency': 'USD',
            'exchange': 'NASDAQ',
            'country': 'United States',
            'website': 'https://www.apple.com',
            'longBusinessSummary': 'Apple Inc. designs, manufactures...'
        }
        
        stock_info = self.processor.process_stock_info(mock_ticker, "AAPL")
        
        self.assertIsInstance(stock_info, StockInfo)
        self.assertEqual(stock_info.symbol, "AAPL")
        self.assertEqual(stock_info.company_name, 'Apple Inc.')
        self.assertEqual(stock_info.sector, 'Technology')
        self.assertEqual(stock_info.market_cap, 3000000000000)
    
    def test_validate_data(self):
        """测试数据验证"""
        # 测试None数据
        self.assertFalse(self.processor.validate_data(None))
        
        # 测试空DataFrame
        mock_empty_df = Mock()
        mock_empty_df.empty = True
        self.assertFalse(self.processor.validate_data(mock_empty_df))
        
        # 测试有效的ticker对象
        mock_ticker = Mock()
        mock_ticker.info = {'symbol': 'AAPL'}
        # 使用spec来确保hasattr正确工作
        mock_ticker = Mock(spec=['info'])
        mock_ticker.info = {'symbol': 'AAPL'}
        self.assertTrue(self.processor.validate_data(mock_ticker))
        
        # 测试有效的DataFrame
        mock_df = Mock()
        mock_df.empty = False
        mock_df.index = [1, 2, 3]  # 非空索引
        self.assertTrue(self.processor.validate_data(mock_df))


class TestYFinanceStockDataProvider(unittest.TestCase):
    """测试yfinance股票数据提供者"""
    
    def setUp(self):
        """设置测试环境"""
        self.cache = MemoryCache()
        self.rate_limiter = SimpleRateLimiter(max_requests=10, time_window=60)
        self.processor = YFinanceDataProcessor()
        self.provider = YFinanceStockDataProvider(
            cache=self.cache,
            rate_limiter=self.rate_limiter,
            data_processor=self.processor
        )
    
    def test_generate_cache_key(self):
        """测试缓存键生成"""
        key = self.provider._generate_cache_key(
            "test_operation",
            symbol="AAPL",
            start_date="2023-01-01",
            param=None
        )
        
        expected = "test_operation:start_date=2023-01-01:symbol=AAPL"
        self.assertEqual(key, expected)
    
    def test_validate_symbol(self):
        """测试股票代码验证"""
        with patch('yfinance.Ticker') as mock_ticker_class:
            mock_ticker = Mock()
            mock_ticker.info = {'symbol': 'AAPL'}
            mock_ticker_class.return_value = mock_ticker
            
            result = self.provider.validate_symbol("AAPL")
            self.assertTrue(result)
    
    def test_validate_symbol_invalid(self):
        """测试无效股票代码验证"""
        with patch('yfinance.Ticker') as mock_ticker_class:
            mock_ticker = Mock()
            mock_ticker.info = {}
            mock_ticker_class.return_value = mock_ticker
            
            result = self.provider.validate_symbol("INVALID")
            self.assertFalse(result)
    
    def test_get_supported_symbols(self):
        """测试获取支持的股票代码"""
        symbols = self.provider.get_supported_symbols()
        
        self.assertIsInstance(symbols, list)
        self.assertGreater(len(symbols), 0)
        self.assertIn('AAPL', symbols)
        self.assertIn('GOOGL', symbols)
    
    @patch('yfinance.Ticker')
    def test_get_stock_info_success(self, mock_ticker_class):
        """测试成功获取股票信息"""
        mock_ticker = Mock()
        mock_ticker.info = {
            'longName': 'Apple Inc.',
            'sector': 'Technology',
            'symbol': 'AAPL'
        }
        mock_ticker_class.return_value = mock_ticker
        
        with patch.object(self.processor, 'validate_data', return_value=True):
            with patch.object(self.processor, 'process_stock_info') as mock_process:
                mock_stock_info = StockInfo(symbol="AAPL", company_name="Apple Inc.")
                mock_process.return_value = mock_stock_info
                
                result = self.provider.get_stock_info("AAPL")
                
                self.assertIsInstance(result, StockInfo)
                self.assertEqual(result.symbol, "AAPL")
    
    @patch('yfinance.Ticker')
    def test_get_stock_info_failure(self, mock_ticker_class):
        """测试获取股票信息失败"""
        mock_ticker_class.side_effect = Exception("Network error")
        
        with self.assertRaises(StockDataError) as context:
            self.provider.get_stock_info("AAPL")
        
        self.assertEqual(context.exception.error_code, "API_ERROR")
    
    def test_search_symbols(self):
        """测试搜索股票代码"""
        with patch.object(self.provider, 'get_stock_info') as mock_get_info:
            mock_get_info.return_value = StockInfo(
                symbol="AAPL",
                company_name="Apple Inc."
            )
            
            results = self.provider.search_symbols("AAPL", limit=5)
            
            self.assertIsInstance(results, list)
            self.assertGreater(len(results), 0)
            
            result = results[0]
            self.assertIn('symbol', result)
            self.assertIn('name', result)


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.provider = YFinanceStockDataProvider()
    
    @patch('yfinance.Ticker')
    def test_full_workflow(self, mock_ticker_class):
        """测试完整工作流程"""
        # 模拟yfinance Ticker
        mock_ticker = Mock()
        mock_ticker.info = {
            'longName': 'Apple Inc.',
            'sector': 'Technology',
            'symbol': 'AAPL',
            'currentPrice': 150.0,
            'previousClose': 148.0
        }
        
        # 模拟历史数据
        mock_hist = Mock()
        mock_hist.empty = False
        mock_hist.iterrows.return_value = [
            (datetime(2023, 1, 1), {
                'Open': 150.0, 'High': 155.0, 'Low': 148.0,
                'Close': 152.0, 'Adj Close': 151.5, 'Volume': 1000000
            })
        ]
        mock_ticker.history.return_value = mock_hist
        mock_ticker_class.return_value = mock_ticker
        
        with patch('yfinance_client.pd.isna', return_value=False):
            with patch.object(self.provider.data_processor, 'validate_data', return_value=True):
                # 测试获取股票信息
                stock_info = self.provider.get_stock_info("AAPL")
                self.assertEqual(stock_info.symbol, "AAPL")
                
                # 测试获取实时价格
                real_time = self.provider.get_real_time_price("AAPL")
                self.assertEqual(real_time.symbol, "AAPL")
                
                # 测试获取历史数据
                historical = self.provider.get_historical_data(
                    symbol="AAPL",
                    period=Period.ONE_MONTH
                )
                self.assertEqual(historical.symbol, "AAPL")
                self.assertGreater(historical.total_count, 0)


def run_performance_tests():
    """运行性能测试"""
    print("\n=== 性能测试 ===")
    
    # 测试缓存性能
    cache = MemoryCache()
    
    # 测试缓存设置性能
    start_time = time.time()
    for i in range(1000):
        cache.set(f"key_{i}", f"value_{i}")
    set_time = time.time() - start_time
    print(f"缓存设置1000个键值对耗时: {set_time:.4f}秒")
    
    # 测试缓存获取性能
    start_time = time.time()
    for i in range(1000):
        cache.get(f"key_{i}")
    get_time = time.time() - start_time
    print(f"缓存获取1000个键值对耗时: {get_time:.4f}秒")
    
    # 测试数据处理性能
    processor = YFinanceDataProcessor()
    
    # 创建模拟数据
    mock_data = []
    for i in range(100):
        mock_data.append((datetime.now() - timedelta(days=i), {
            'Open': 150.0 + i,
            'High': 155.0 + i,
            'Low': 148.0 + i,
            'Close': 152.0 + i,
            'Adj Close': 151.5 + i,
            'Volume': 1000000 + i * 1000
        }))
    
    mock_df = Mock()
    mock_df.empty = False
    mock_df.iterrows.return_value = mock_data
    
    with patch('yfinance_client.pd.isna', return_value=False):
        start_time = time.time()
        response = processor.process_historical_data(mock_df, "TEST")
        process_time = time.time() - start_time
        print(f"处理100条历史记录耗时: {process_time:.4f}秒")
        print(f"处理后记录数: {response.total_count}")


if __name__ == '__main__':
    # 运行单元测试
    unittest.main(verbosity=2, exit=False)
    
    # 运行性能测试
    run_performance_tests()
    
    print("\n=== 测试完成 ===")