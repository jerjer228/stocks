import os
import json
import datetime
import yfinance as yf

WATCHLIST = ["TSLA", "NVDA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "AMD"]
SECTOR_ETFS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLC", "XLB", "XLRE", "XLU"]

def get_quote(symbol):
    """使用 yfinance 抓取即時（含盤前盤後 prepost=True）價格"""
    try:
        ticker = yf.Ticker(symbol)
        # 抓取包含盤前盤後的 1 分鐘線數據
        df = ticker.history(period="1d", interval="1m", prepost=True)
        if df.empty:
            return {}
        
        latest_price = df['Close'].iloc[-1]
        prev_close = ticker.fast_info['previous_close']
        change_pct = ((latest_price - prev_close) / prev_close) * 100
        
        return {
            "c": float(latest_price),
            "dp": float(change_pct),
            "pc": float(prev_close)
        }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return {}

def get_market_session():
    """判斷美股當前時段 (HKT 時間轉換)"""
    now_utc = datetime.datetime.utcnow()
    # 美東時間 (EST = UTC-5)
    est_time = now_utc - datetime.timedelta(hours=5)
    hour = est_time.hour + est_time.minute / 60.0
    weekday = est_time.weekday()

    if weekday >= 5:
        return "週末休市"
    elif 4.0 <= hour < 9.5:
        return "盤前交易 (Pre-Market)"
    elif 9.5 <= hour < 16.0:
        return "盤中交易 (Regular)"
    elif 16.0 <= hour < 20.0:
        return "盤後交易 (After-Hours)"
    else:
        return "休市 (Closed)"

def calculate_market_confidence():
    spy = get_quote("SPY")
    qqq = get_quote("QQQ")
    vix = get_quote("VIX")
    
    score = 0
    spy_change = spy.get("dp", 0)
    qqq_change = qqq.get("dp", 0)
    vix_val = vix.get("c", 18)
    
    if spy_change > 0.5: score += 30
    elif spy_change > 0: score += 20
    elif spy_change > -0.5: score += 10
    
    if qqq_change > 0.5: score += 30
    elif qqq_change > 0: score += 20
    elif qqq_change > -0.5: score += 10
    
    if vix_val < 15: score += 20
    elif vix_val < 20: score += 15
    elif vix_val < 25: score += 5
    
    positive_sectors = sum(1 for s in SECTOR_ETFS if get_quote(s).get("dp", 0) > 0)
    score += int((positive_sectors / len(SECTOR_ETFS)) * 20)
    
    return {
        "confidence_score": min(max(score, 0), 100),
        "spy_status": f"{'漲' if spy_change>0 else '跌'} ({spy_change:+.2f}%)",
        "qqq_status": f"{'漲' if qqq_change>0 else '跌'} ({qqq_change:+.2f}%)",
        "vix_val": f"{vix_val:.2f}",
        "session": get_market_session()
    }

def analyze_watchlist():
    results = []
    for ticker in WATCHLIST:
        q = get_quote(ticker)
        dp = q.get("dp", 0)
        c = q.get("c", 0)
        
        conviction = 80 if dp > 1.5 else (60 if dp > 0 else 40)
        results.append({"ticker": ticker, "change": dp, "price": c, "conviction": conviction})
        
    tonight_trades, long_term_picks, avoid_list = [], [], []
    for r in sorted(results, key=lambda x: x["change"], reverse=True):
        if r["change"] > 1.0:
            tonight_trades.append({"ticker": r["ticker"], "strategy": f"盤前動量 / ${r['price']:.2f}", "conviction": f"{r['conviction']}/100"})
            long_term_picks.append({"ticker": r["ticker"], "reason": "盤前強勢領漲", "score": r["conviction"]})
        elif r["change"] < -1.0:
            avoid_list.append({"ticker": r["ticker"], "reason": "盤前走弱破位", "risk_level": "高風險"})
        else:
            tonight_trades.append({"ticker": r["ticker"], "strategy": f"盤前觀望 / ${r['price']:.2f}", "conviction": "65/100"})

    return tonight_trades[:3], long_term_picks[:3], avoid_list[:3]

def main():
    market_data = calculate_market_confidence()
    tonight_trades, long_term_picks, avoid_list = analyze_watchlist()
    hkt_now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    
    dashboard_data = {
        "last_updated": hkt_now.strftime("%Y-%m-%d %H:%M:%S"),
        "market": market_data,
        "tonight_trades": tonight_trades,
        "long_term_picks": long_term_picks,
        "avoid_list": avoid_list
    }
    
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(dashboard_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

import pandas as pd
import yfinance as yf

# 範例：從 S&P 500 或特定Watchlist中篩選
TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "AMD", "PLTR", "INTC"] # 可擴充至全美股

def get_top_10_recommendations(tickers):
    recommendations = []
    
    for ticker in tickers:
        df = yf.Ticker(ticker).history(period="60d")
        if df.empty:
            continue
            
        # 計算基礎技術指標
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        
        last_price = df['Close'].iloc[-1]
        sma20 = df['SMA20'].iloc[-1]
        sma50 = df['SMA50'].iloc[-1]
        volume_ratio = df['Volume'].iloc[-1] / df['Volume'].mean()
        
        # 簡單評分邏輯 (例如：突破 20SMA + 成交量放大)
        score = 0
        if last_price > sma20: score += 40
        if sma20 > sma50: score += 30
        if volume_ratio > 1.2: score += 30
        
        signal = "Strong Buy" if score >= 80 else ("Buy" if score >= 60 else "Watch")
        
        recommendations.append({
            "ticker": ticker,
            "price": round(last_price, 2),
            "score": score,
            "signal": signal,
            "volume_ratio": round(volume_ratio, 2)
        })
    
    # 按分數排序，取 Top 10
    recommendations = sorted(recommendations, key=lambda x: x['score'], reverse=True)[:10]
    return recommendations
