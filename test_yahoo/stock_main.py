#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票数据获取主程序

本程序提供命令行接口，用于获取股票的历史数据和实时价格信息。
支持多种输出格式（表格、JSON、CSV）和灵活的参数配置。
"""

import sys
import json
import argparse
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from yfinance_client import YFinanceStockDataProvider
from stock_models import StockDataError, TimeInterval, Period


def setup_logging(verbose: bool = False):
    """设置日志配置"""
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def parse_date(date_str: str) -> date:
    """解析日期字符串"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"无效的日期格式: {date_str}，请使用 YYYY-MM-DD 格式")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='获取股票历史数据和实时价格信息',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s AAPL                           # 获取苹果公司的基本信息和实时价格
  %(prog)s AAPL --historical              # 获取苹果公司的历史数据（默认1年）
  %(prog)s GOOGL --start 2023-01-01       # 获取谷歌从2023年开始的历史数据
  %(prog)s MSFT --period 6mo --interval 1wk  # 获取微软6个月的周线数据
  %(prog)s TSLA --output json             # 以JSON格式输出特斯拉的数据
  %(prog)s --search apple                 # 搜索包含'apple'的股票
        """
    )
    
    # 位置参数
    parser.add_argument(
        'symbol',
        nargs='?',
        help='股票代码 (例如: AAPL, GOOGL, MSFT)'
    )
    
    # 数据类型选项
    data_group = parser.add_mutually_exclusive_group()
    data_group.add_argument(
        '--historical',
        action='store_true',
        help='获取历史数据'
    )
    data_group.add_argument(
        '--realtime',
        action='store_true',
        help='获取实时价格（默认）'
    )
    data_group.add_argument(
        '--info',
        action='store_true',
        help='获取股票基本信息'
    )
    data_group.add_argument(
        '--search',
        metavar='QUERY',
        help='搜索股票代码'
    )
    
    # 历史数据参数
    hist_group = parser.add_argument_group('历史数据选项')
    hist_group.add_argument(
        '--start',
        type=parse_date,
        help='开始日期 (YYYY-MM-DD)'
    )
    hist_group.add_argument(
        '--end',
        type=parse_date,
        help='结束日期 (YYYY-MM-DD)'
    )
    hist_group.add_argument(
        '--period',
        choices=[p.value for p in Period],
        help='数据周期 (与start/end互斥)'
    )
    hist_group.add_argument(
        '--interval',
        choices=[i.value for i in TimeInterval],
        default=TimeInterval.ONE_DAY.value,
        help='时间间隔 (默认: 1d)'
    )
    
    # 输出选项
    parser.add_argument(
        '--output',
        choices=['table', 'json', 'csv'],
        default='table',
        help='输出格式 (默认: table)'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='限制输出的记录数量'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='显示详细信息'
    )
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging(args.verbose)
    
    # 检查参数
    if not args.symbol and not args.search:
        parser.error("请提供股票代码或使用 --search 搜索股票")
    
    if args.start and args.end and args.start > args.end:
        parser.error("开始日期不能晚于结束日期")
    
    if (args.start or args.end) and args.period:
        parser.error("--start/--end 与 --period 不能同时使用")
    
    try:
        # 创建数据提供者
        provider = YFinanceStockDataProvider()
        
        # 处理搜索请求
        if args.search:
            results = provider.search_symbols(args.search)
            if args.output == 'json':
                print(json.dumps(results, indent=2, ensure_ascii=False))
            else:
                print(f"\n搜索结果 (关键词: {args.search}):")
                print("-" * 50)
                for result in results:
                    print(f"{result['symbol']:<10} {result['name']}")
            return 0
        
        # 验证股票代码
        if not provider.validate_symbol(args.symbol):
            print(f"错误: 无效的股票代码 '{args.symbol}'", file=sys.stderr)
            return 1
        
        # 根据请求类型获取数据
        if args.info:
            # 获取股票信息
            stock_info = provider.get_stock_info(args.symbol)
            output_stock_info(stock_info, args.output)
            
        elif args.historical:
            # 获取历史数据
            period_obj = Period(args.period) if args.period else None
            interval_obj = TimeInterval(args.interval)
            
            response = provider.get_historical_data(
                symbol=args.symbol,
                start_date=args.start,
                end_date=args.end,
                period=period_obj,
                interval=interval_obj
            )
            
            # 应用限制
            if args.limit and response.price_data:
                response.price_data = response.price_data[-args.limit:]
                response.total_count = len(response.price_data)
            
            output_historical_data(response, args.output)
            
        else:
            # 获取实时价格（默认）
            real_time_price = provider.get_real_time_price(args.symbol)
            output_real_time_price(real_time_price, args.output)
        
        return 0
        
    except StockDataError as e:
        print(f"数据错误: {e.message} (代码: {e.error_code})", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n操作被用户取消", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"未知错误: {str(e)}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def output_stock_info(stock_info, output_format):
    """输出股票信息"""
    if output_format == 'json':
        print(json.dumps(stock_info.dict(), indent=2, ensure_ascii=False, default=str))
    elif output_format == 'csv':
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头和数据
        for key, value in stock_info.dict().items():
            writer.writerow([key, value])
        
        print(output.getvalue())
    else:
        # 表格格式
        print(f"\n股票信息: {stock_info.symbol}")
        print("=" * 50)
        
        info_items = [
            ('公司名称', stock_info.company_name),
            ('行业', stock_info.sector),
            ('细分行业', stock_info.industry),
            ('市值', f"${stock_info.market_cap:,.0f}" if stock_info.market_cap else None),
            ('货币', stock_info.currency),
            ('交易所', stock_info.exchange),
            ('国家', stock_info.country),
            ('官网', stock_info.website)
        ]
        
        for label, value in info_items:
            if value:
                print(f"{label:<12}: {value}")
        
        if stock_info.description:
            print(f"\n公司描述:")
            print("-" * 20)
            # 限制描述长度
            desc = stock_info.description[:500] + "..." if len(stock_info.description) > 500 else stock_info.description
            print(desc)


def output_historical_data(response, output_format):
    """输出历史数据"""
    if output_format == 'json':
        print(json.dumps(response.dict(), indent=2, ensure_ascii=False, default=str))
    elif output_format == 'csv':
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        writer.writerow([
            '日期', '开盘价', '最高价', '最低价', '收盘价', '调整收盘价', '成交量'
        ])
        
        # 写入数据
        for price_data in response.price_data:
            writer.writerow([
                price_data.timestamp.strftime('%Y-%m-%d'),
                price_data.open_price,
                price_data.high_price,
                price_data.low_price,
                price_data.close_price,
                price_data.adjusted_close,
                price_data.volume
            ])
        
        print(output.getvalue())
    else:
        # 表格格式
        print(f"\n历史数据: {response.symbol}")
        if response.stock_info and response.stock_info.company_name:
            print(f"公司: {response.stock_info.company_name}")
        print(f"数据记录数: {response.total_count}")
        print(f"时间间隔: {response.interval.value}")
        if response.start_date and response.end_date:
            print(f"日期范围: {response.start_date} 到 {response.end_date}")
        print(f"最后更新: {response.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if not response.price_data:
            print("\n没有找到历史数据")
            return
        
        print("\n历史价格数据:")
        print("-" * 100)
        print(f"{'日期':<12} {'开盘价':<10} {'最高价':<10} {'最低价':<10} {'收盘价':<10} {'调整收盘':<10} {'成交量':<15}")
        print("-" * 100)
        
        for price_data in response.price_data:
            date_str = price_data.timestamp.strftime('%Y-%m-%d')
            open_price = f"${price_data.open_price:.2f}" if price_data.open_price else "N/A"
            high_price = f"${price_data.high_price:.2f}" if price_data.high_price else "N/A"
            low_price = f"${price_data.low_price:.2f}" if price_data.low_price else "N/A"
            close_price = f"${price_data.close_price:.2f}" if price_data.close_price else "N/A"
            adj_close = f"${price_data.adjusted_close:.2f}" if price_data.adjusted_close else "N/A"
            volume = f"{price_data.volume:,}" if price_data.volume else "N/A"
            
            print(f"{date_str:<12} {open_price:<10} {high_price:<10} {low_price:<10} {close_price:<10} {adj_close:<10} {volume:<15}")


def output_real_time_price(real_time_price, output_format):
    """输出实时价格"""
    if output_format == 'json':
        print(json.dumps(real_time_price.dict(), indent=2, ensure_ascii=False, default=str))
    elif output_format == 'csv':
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头和数据
        writer.writerow([
            '股票代码', '当前价格', '前收盘价', '价格变化', '变化百分比', '成交量',
            '市值', '市盈率', '日内最高', '日内最低', '52周最高', '52周最低', '更新时间'
        ])
        
        writer.writerow([
            real_time_price.symbol,
            real_time_price.current_price,
            real_time_price.previous_close,
            real_time_price.change,
            real_time_price.change_percent,
            real_time_price.volume,
            real_time_price.market_cap,
            real_time_price.pe_ratio,
            real_time_price.day_high,
            real_time_price.day_low,
            real_time_price.fifty_two_week_high,
            real_time_price.fifty_two_week_low,
            real_time_price.last_updated.strftime('%Y-%m-%d %H:%M:%S')
        ])
        
        print(output.getvalue())
    else:
        # 表格格式
        print(f"\n实时价格: {real_time_price.symbol}")
        print("=" * 50)
        
        # 价格信息
        print(f"当前价格: ${real_time_price.current_price:.2f}")
        
        if real_time_price.previous_close:
            print(f"前收盘价: ${real_time_price.previous_close:.2f}")
        
        if real_time_price.change is not None:
            change_sign = "+" if real_time_price.change >= 0 else ""
            print(f"价格变化: {change_sign}${real_time_price.change:.2f}")
        
        if real_time_price.change_percent is not None:
            change_sign = "+" if real_time_price.change_percent >= 0 else ""
            print(f"变化百分比: {change_sign}{real_time_price.change_percent:.2f}%")
        
        # 其他信息
        info_items = [
            ('成交量', f"{real_time_price.volume:,}" if real_time_price.volume else None),
            ('市值', f"${real_time_price.market_cap:,.0f}" if real_time_price.market_cap else None),
            ('市盈率', f"{real_time_price.pe_ratio:.2f}" if real_time_price.pe_ratio else None),
            ('日内最高', f"${real_time_price.day_high:.2f}" if real_time_price.day_high else None),
            ('日内最低', f"${real_time_price.day_low:.2f}" if real_time_price.day_low else None),
            ('52周最高', f"${real_time_price.fifty_two_week_high:.2f}" if real_time_price.fifty_two_week_high else None),
            ('52周最低', f"${real_time_price.fifty_two_week_low:.2f}" if real_time_price.fifty_two_week_low else None)
        ]
        
        print()
        for label, value in info_items:
            if value:
                print(f"{label:<12}: {value}")
        
        print(f"\n更新时间: {real_time_price.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")


def demo():
    """演示程序功能"""
    print("=== yfinance股票数据获取程序演示 ===")
    
    # 创建数据提供者
    provider = YFinanceStockDataProvider()
    
    # 演示支持的股票代码
    print("\n支持的股票代码示例:")
    symbols = provider.get_supported_symbols()
    print(", ".join(symbols[:10]))
    
    # 演示获取数据
    test_symbol = "AAPL"
    print(f"\n正在获取 {test_symbol} 的数据...")
    
    try:
        # 获取股票信息
        stock_info = provider.get_stock_info(test_symbol)
        print(f"\n公司信息:")
        print(f"名称: {stock_info.company_name}")
        print(f"行业: {stock_info.sector}")
        
        # 获取实时价格
        real_time = provider.get_real_time_price(test_symbol)
        print(f"\n实时价格: ${real_time.current_price:.2f}")
        
        # 获取历史数据
        historical = provider.get_historical_data(
            symbol=test_symbol,
            period=Period.ONE_MONTH
        )
        print(f"\n历史数据: {historical.total_count} 条记录")
        
        if historical.price_data:
            latest = historical.price_data[-1]
            print(f"最新收盘价: ${latest.close_price:.2f} ({latest.timestamp.strftime('%Y-%m-%d')})")
        
    except StockDataError as e:
        print(f"演示失败: {e.message}")
        print("注意: 这是一个演示程序，需要网络连接")


if __name__ == '__main__':
    if len(sys.argv) == 1:
        # 如果没有参数，运行演示
        demo()
    else:
        # 否则运行主程序
        sys.exit(main())