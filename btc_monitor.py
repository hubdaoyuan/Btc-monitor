#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC价格监控系统
功能：获取BTC价格、K线数据、计算支撑阻力位、分析市场情绪，并通过Server酱推送微信通知
"""

import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# ==================== 配置 ====================
# 多个API备用，避免单一API被墙
API_SOURCES = [
    {"name": "Binance", "base": "https://api.binance.com", "kline": "/api/v3/klines", "ticker": "/api/v3/ticker/24hr"},
    {"name": "Binance2", "base": "https://api1.binance.com", "kline": "/api/v3/klines", "ticker": "/api/v3/ticker/24hr"},
    {"name": "Binance3", "base": "https://data-api.binance.vision", "kline": "/api/v3/klines", "ticker": "/api/v3/ticker/24hr"},
]
SERVERCHAN_API = "https://sctapi.ftqq.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# ==================== 数据获取 ====================

def get_btc_price() -> Dict:
    """获取BTC当前价格，自动尝试多个API源"""
    for source in API_SOURCES:
        try:
            url = f"{source['base']}{source['ticker']}"
            response = requests.get(
                url,
                params={"symbol": "BTCUSDT"},
                headers=HEADERS,
                timeout=10
            )
            data = response.json()
            if "lastPrice" in data:
                print(f"  数据源: {source['name']}")
                return {
                    "price": float(data["lastPrice"]),
                    "change_24h": float(data["priceChange"]),
                    "change_percent": float(data["priceChangePercent"]),
                    "high_24h": float(data["highPrice"]),
                    "low_24h": float(data["lowPrice"]),
                    "volume": float(data["volume"]),
                    "quote_volume": float(data["quoteVolume"])
                }
            else:
                print(f"  {source['name']} 返回异常: {data.get('msg', data.get('code', 'unknown'))}")
        except Exception as e:
            print(f"  {source['name']} 请求失败: {e}")
    
    # 所有Binance API都失败，尝试CoinGecko备用
    try:
        print("  尝试CoinGecko备用源...")
        cg_url = "https://api.coingecko.com/api/v3/simple/price"
        response = requests.get(cg_url, params={"ids": "bitcoin", "vs_currencies": "usdt", "include_24hr_change": "true", "include_24hr_vol": "true"}, headers=HEADERS, timeout=10)
        data = response.json().get("bitcoin", {})
        if data:
            price = data.get("usdt", 0)
            change = data.get("usdt_24h_change", 0)
            vol = data.get("usdt_24h_vol", 0)
            return {
                "price": price,
                "change_24h": price * change / 100 if change else 0,
                "change_percent": change if change else 0,
                "high_24h": 0,
                "low_24h": 0,
                "volume": 0,
                "quote_volume": vol
            }
    except Exception as e:
        print(f"  CoinGecko 也失败: {e}")
    
    print("获取BTC价格失败: 所有数据源均不可用")
    return {}

def get_kline_data(interval: str = "1d", limit: int = 30) -> pd.DataFrame:
    """获取K线数据，自动尝试多个API源
    
    Args:
        interval: K线周期 (1m, 5m, 15m, 1h, 4h, 1d, 1w)
        limit: 获取条数
    """
    for source in API_SOURCES:
        try:
            url = f"{source['base']}{source['kline']}"
            response = requests.get(
                url,
                params={
                    "symbol": "BTCUSDT",
                    "interval": interval,
                    "limit": limit
                },
                headers=HEADERS,
                timeout=10
            )
            data = response.json()
            
            # 检查返回的是否是有效K线数据
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                df = pd.DataFrame(data, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume', 'trades', 'taker_buy_volume',
                    'taker_buy_quote_volume', 'ignore'
                ])
                
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)
                
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                print(f"  K线数据源: {source['name']}")
                return df[['open', 'high', 'low', 'close', 'volume']]
            else:
                print(f"  {source['name']} K线返回异常")
        except Exception as e:
            print(f"  {source['name']} K线请求失败: {e}")
    
    print("获取K线数据失败: 所有数据源均不可用")
    return pd.DataFrame()

# ==================== 技术分析 ====================

def calculate_sma(data: pd.Series, period: int) -> pd.Series:
    """计算简单移动平均线"""
    return data.rolling(window=period).mean()

def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """计算指数移动平均线"""
    return data.ewm(span=period, adjust=False).mean()

def calculate_rsi(data: pd.Series, period: int = 14) -> float:
    """计算RSI指标"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50

def calculate_support_resistance(df: pd.DataFrame, window: int = 10) -> Tuple[float, float]:
    """计算支撑和阻力位
    
    使用近期高点和低点来计算
    """
    if len(df) < window:
        return 0, 0
    
    recent_data = df.tail(window)
    
    # 阻力位：近期高点
    resistance = recent_data['high'].max()
    
    # 支撑位：近期低点
    support = recent_data['low'].min()
    
    return support, resistance

def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Dict:
    """计算布林带"""
    sma = calculate_sma(df['close'], period)
    std = df['close'].rolling(window=period).std()
    
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    
    return {
        'upper': upper_band.iloc[-1],
        'middle': sma.iloc[-1],
        'lower': lower_band.iloc[-1]
    }

def analyze_trend(df: pd.DataFrame) -> str:
    """分析趋势"""
    if len(df) < 20:
        return "数据不足"
    
    # 计算均线
    ma7 = calculate_sma(df['close'], 7).iloc[-1]
    ma20 = calculate_sma(df['close'], 20).iloc[-1]
    current_price = df['close'].iloc[-1]
    
    # 趋势判断
    if current_price > ma7 > ma20:
        return "强势上涨"
    elif current_price > ma20:
        return "上涨趋势"
    elif current_price < ma7 < ma20:
        return "强势下跌"
    elif current_price < ma20:
        return "下跌趋势"
    else:
        return "震荡整理"

# ==================== 市场情绪 ====================

def calculate_fear_greed_index(price_data: pd.DataFrame) -> Dict:
    """计算简单的恐惧贪婪指数（0-100）
    
    基于多个指标综合计算：
    - RSI
    - 价格相对于近期高低点的位置
    - 成交量变化
    """
    if len(price_data) < 14:
        return {"value": 50, "label": "中性", "description": "数据不足"}
    
    # RSI成分 (0-30 恐惧, 70-100 贪婪)
    rsi = calculate_rsi(price_data['close'])
    rsi_score = 100 - rsi  # RSI低=贪婪，RSI高=恐惧
    
    # 价格动量成分
    recent_high = price_data['high'].tail(14).max()
    recent_low = price_data['low'].tail(14).min()
    current_price = price_data['close'].iloc[-1]
    
    if recent_high > recent_low:
        price_position = (current_price - recent_low) / (recent_high - recent_low) * 100
    else:
        price_position = 50
    
    # 综合计算（各50%权重）
    fear_greed_value = (rsi_score * 0.5 + price_position * 0.5)
    
    # 标签
    if fear_greed_value <= 20:
        label = "极度恐惧"
    elif fear_greed_value <= 40:
        label = "恐惧"
    elif fear_greed_value <= 60:
        label = "中性"
    elif fear_greed_value <= 80:
        label = "贪婪"
    else:
        label = "极度贪婪"
    
    return {
        "value": round(fear_greed_value, 1),
        "label": label,
        "rsi": round(rsi, 1),
        "price_position": round(price_position, 1)
    }

# ==================== 图表生成 ====================

def generate_kline_chart(df: pd.DataFrame, output_path: str = "btc_kline.png"):
    """生成K线图"""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.patches import Rectangle
        
        fig, axes = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]})
        ax1, ax2 = axes
        
        # 绘制K线
        for i, (idx, row) in enumerate(df.iterrows()):
            color = '#26a69a' if row['close'] >= row['open'] else '#ef5350'
            
            # 实体
            height = abs(row['close'] - row['open'])
            bottom = min(row['close'], row['open'])
            rect = Rectangle((i - 0.4, bottom), 0.8, height, 
                           facecolor=color, edgecolor=color, linewidth=1)
            ax1.add_patch(rect)
            
            # 影线
            ax1.plot([i, i], [row['low'], row['high']], color=color, linewidth=1)
        
        # 添加移动平均线
        if len(df) >= 7:
            ma7 = calculate_sma(df['close'], 7)
            ax1.plot(range(len(df)), ma7, color='#ff9800', linewidth=1.5, label='MA7')
        
        if len(df) >= 20:
            ma20 = calculate_sma(df['close'], 20)
            ax1.plot(range(len(df)), ma20, color='#2196f3', linewidth=1.5, label='MA20')
        
        # 设置K线图表
        ax1.set_title('BTC/USDT K线图', fontsize=16, fontweight='bold')
        ax1.set_ylabel('价格 (USDT)', fontsize=12)
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        ax1.set_xticks(range(0, len(df), 5))
        ax1.set_xticklabels([d.strftime('%m-%d') for d in df.index[::5]], rotation=45)
        
        # 绘制成交量
        colors = ['#26a69a' if df['close'].iloc[i] >= df['open'].iloc[i] else '#ef5350' 
                  for i in range(len(df))]
        ax2.bar(range(len(df)), df['volume'], color=colors, alpha=0.7)
        ax2.set_ylabel('成交量', fontsize=12)
        ax2.set_xlabel('日期', fontsize=12)
        ax2.grid(True, alpha=0.3)
        ax2.set_xticks(range(0, len(df), 5))
        ax2.set_xticklabels([d.strftime('%m-%d') for d in df.index[::5]], rotation=45)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        
        print(f"K线图已保存至: {output_path}")
        return output_path
    except Exception as e:
        print(f"生成K线图失败: {e}")
        return None

# ==================== 推送通知 ====================

def send_wechat_notification(sendkey: str, title: str, content: str) -> bool:
    """通过Server酱发送微信推送通知"""
    try:
        url = f"{SERVERCHAN_API}/{sendkey}.send"
        data = {
            "title": title,
            "desp": content
        }
        response = requests.post(url, data=data, timeout=10)
        result = response.json()
        
        if result.get("code") == 0:
            print("微信推送发送成功！")
            return True
        else:
            print(f"微信推送失败: {result.get('message')}")
            return False
    except Exception as e:
        print(f"发送微信推送时出错: {e}")
        return False

# ==================== 报告生成 ====================

def generate_report() -> Dict:
    """生成完整的BTC监控报告"""
    print("=" * 50)
    print("开始生成BTC监控报告...")
    print("=" * 50)
    
    # 1. 获取当前价格
    print("\n📊 获取BTC当前价格...")
    price_data = get_btc_price()
    if not price_data:
        return {"error": "无法获取BTC价格数据"}
    
    # 2. 获取K线数据
    print("📈 获取K线数据...")
    daily_df = get_kline_data("1d", 30)
    weekly_df = get_kline_data("1w", 12)
    
    if daily_df.empty:
        return {"error": "无法获取K线数据"}
    
    # 3. 技术分析
    print("🔍 进行技术分析...")
    support, resistance = calculate_support_resistance(daily_df)
    trend = analyze_trend(daily_df)
    rsi = calculate_rsi(daily_df['close'])
    
    # 布林带
    bb = calculate_bollinger_bands(daily_df)
    
    # 4. 市场情绪
    print("😊 分析市场情绪...")
    sentiment = calculate_fear_greed_index(daily_df)
    
    # 5. 生成图表
    print("🎨 生成K线图...")
    chart_path = generate_kline_chart(daily_df)
    
    # 6. 构建报告
    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "price": price_data,
        "ohlc": {
            "open": daily_df['open'].iloc[-1],
            "high": daily_df['high'].iloc[-1],
            "low": daily_df['low'].iloc[-1],
            "close": daily_df['close'].iloc[-1]
        },
        "support_resistance": {
            "support": round(support, 2),
            "resistance": round(resistance, 2)
        },
        "technical": {
            "trend": trend,
            "rsi": round(rsi, 2),
            "bollinger_bands": {k: round(v, 2) for k, v in bb.items()}
        },
        "sentiment": sentiment,
        "chart_path": chart_path
    }
    
    print("\n✅ 报告生成完成！")
    return report

def format_wechat_message(report: Dict) -> str:
    """格式化微信推送消息"""
    price = report.get("price", {})
    ohlc = report.get("ohlc", {})
    sr = report.get("support_resistance", {})
    tech = report.get("technical", {})
    sentiment = report.get("sentiment", {})
    
    change_emoji = "🟢" if price.get("change_percent", 0) >= 0 else "🔴"
    sentiment_emoji = {
        "极度恐惧": "😱",
        "恐惧": "😰",
        "中性": "😐",
        "贪婪": "🤑",
        "极度贪婪": "🚀"
    }.get(sentiment.get("label", "中性"), "😐")
    
    message = f"""
**BTC 价格监控报告**
⏰ 更新时间：{report.get('timestamp')}

**💰 价格信息**
• 当前价格：${price.get('price', 0):,.2f}
• 24h涨跌：{change_emoji} {price.get('change_percent', 0):+.2f}%
• 24h最高：${price.get('high_24h', 0):,.2f}
• 24h最低：${price.get('low_24h', 0):,.2f}
• 24h成交量：{price.get('volume', 0)/1e8:.2f}亿 USDT

**📊 今日OHLC**
• 开盘：${ohlc.get('open', 0):,.2f}
• 最高：${ohlc.get('high', 0):,.2f}
• 最低：${ohlc.get('low', 0):,.2f}
• 收盘：${ohlc.get('close', 0):,.2f}

**🎯 关键价位**
• 支撑位：${sr.get('support', 0):,.2f}
• 阻力位：${sr.get('resistance', 0):,.2f}

**📈 技术指标**
• 趋势：{tech.get('trend', 'N/A')}
• RSI：{tech.get('rsi', 0):.2f}
• 布林上轨：${tech.get('bollinger_bands', {}).get('upper', 0):,.2f}
• 布林中轨：${tech.get('bollinger_bands', {}).get('middle', 0):,.2f}
• 布林下轨：${tech.get('bollinger_bands', {}).get('lower', 0):,.2f}

**{sentiment_emoji} 市场情绪**
• 恐惧贪婪指数：{sentiment.get('value', 0):.1f}/100
• 情绪状态：{sentiment.get('label', 'N/A')}
• RSI指标：{sentiment.get('rsi', 0):.1f}

---
💡 提示：本报告仅供参考，不构成投资建议
"""
    return message

# ==================== 主程序 ====================

def main():
    """主函数"""
    # 从环境变量获取配置
    sendkey = os.environ.get("SERVERCHAN_SENDKEY", "")
    
    # 生成报告
    report = generate_report()
    
    if "error" in report:
        print(f"❌ 错误: {report['error']}")
        return
    
    # 打印报告摘要
    print("\n" + "=" * 50)
    print("📋 报告摘要")
    print("=" * 50)
    print(f"BTC价格: ${report['price']['price']:,.2f}")
    print(f"24h涨跌: {report['price']['change_percent']:+.2f}%")
    print(f"趋势: {report['technical']['trend']}")
    print(f"市场情绪: {report['sentiment']['label']} ({report['sentiment']['value']:.1f})")
    
    # 发送微信推送
    if sendkey:
        print("\n📤 发送微信推送...")
        title = f"BTC监控 | ${report['price']['price']:,.0f} | {report['price']['change_percent']:+.2f}%"
        content = format_wechat_message(report)
        send_wechat_notification(sendkey, title, content)
    else:
        print("\n⚠️ 未配置Server酱SendKey，跳过微信推送")
        print("💡 如需推送，请设置环境变量 SERVERCHAN_SENDKEY")

if __name__ == "__main__":
    main()
