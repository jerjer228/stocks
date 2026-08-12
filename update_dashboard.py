import os
import json
import datetime
import requests

# 從 GitHub Secrets 讀取 Finnhub API Key
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

# 設定關注的自選股池與板塊 ETF
WATCHLIST = ["TSLA", "NVDA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "AMD"]
SECTOR_ETFS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLC", "XLB", "XLRE", "XLU"]

def get_quote(symbol):
    """呼叫 Finnhub API 抓取標的當前報價與單日漲跌幅"""
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    try:
        r = requests.get(url, timeout=10).json()
        return r
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return {}

def calculate_market_confidence():
    """
    計算 0-100 信心指數 logic：
    1. SPY 漲跌幅與動量 (最高 30 分)
    2. QQQ 漲跌幅與動量 (最高 30 分)
    3. VIX 恐慌指數 (最高 20 分)
    4. 11大板塊輪動健康度 (最高 20 分)
    """
    spy = get_quote("SPY")
    qqq = get_quote("QQQ")
    vix = get_quote("VIX")
    
    score = 0
    
    # 1. SPY 評分
    spy_change = spy.get("dp", 0)
    if spy_change > 0.5: score += 30
    elif spy_change > 0: score += 20
    elif spy_change > -0.5: score += 10
    
    # 2. QQQ 評分
    qqq_change = qqq.get("dp", 0)
    if qqq_change > 0.5: score += 30
    elif qqq_change > 0: score += 20
    elif qqq_change > -0.5: score += 10
    
    # 3. VIX 評分 (波動率越低，分數越高)
    vix_val = vix.get("c", 18)
    if vix_val < 15: score += 20
    elif vix_val < 20: score += 15
    elif vix_val < 25: score += 5
    
    # 4. 板塊輪動健康度 (統計 11 個 Sector ETF 有多少個處於上漲狀態)
    positive_sectors = 0
    for s in SECTOR_ETFS:
        q = get_quote(s)
        if q.get("dp", 0) > 0:
            positive_sectors += 1
    
    sector_score = int((positive_sectors / len(SECTOR_ETFS)) * 20)
    score += sector_score
    
    spy_status = "多頭強勢" if spy_change > 0 else "空頭修整"
    qqq_status = "多頭強勢" if qqq_change > 0 else "空頭修整"
    
    return {
        "confidence_score": min(max(score, 0), 100),
        "spy_status": f"{spy_status} ({spy_change:+.2f}%)",
        "qqq_status": f"{qqq_status} ({qqq_change:+.2f}%)",
        "vix_val": f"{vix_val:.2f}"
    }

def analyze_watchlist():
    """對自選股池進行量化篩選，分類輸出至卡片 2、3、4"""
    results = []
    for ticker in WATCHLIST:
        q = get_quote(ticker)
        dp = q.get("dp", 0)
        c = q.get("c", 0)
        
        # 根據漲跌幅計算 Conviction 分數
        conviction = 80 if dp > 1.5 else (60 if dp > 0 else 40)
        results.append({
            "ticker": ticker,
            "change": dp,
            "price": c,
            "conviction": conviction
        })
        
    tonight_trades = []
    long_term_picks = []
    avoid_list = []
    
    # 依漲跌幅降序排列
    for r in sorted(results, key=lambda x: x["change"], reverse=True):
        if r["change"] > 1.0:
            tonight_trades.append({
                "ticker": r["ticker"],
                "strategy": "動量突破 / Call Option",
                "conviction": f"{r['conviction']}/100"
            })
            long_term_picks.append({
                "ticker": r["ticker"],
                "reason": "強勢板塊領跑標的",
                "score": r["conviction"]
            })
        elif r["change"] < -1.0:
            avoid_list.append({
                "ticker": r["ticker"],
                "reason": "單日技術破位，暫避觀望",
                "risk_level": "高風險"
            })
        else:
            tonight_trades.append({
                "ticker": r["ticker"],
                "strategy": "區間低吸 / Covered Call",
                "conviction": "65/100"
            })

    # 確保每個卡片傳回前 3 個標的
    return tonight_trades[:3], long_term_picks[:3], avoid_list[:3]

def main():
    market_data = calculate_market_confidence()
    tonight_trades, long_term_picks, avoid_list = analyze_watchlist()
    
    # 取得當前 HKT 時間 (UTC+8)
    hkt_now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    
    dashboard_data = {
        "last_updated": hkt_now.strftime("%Y-%m-%d %H:%M:%S"),
        "market": market_data,
        "tonight_trades": tonight_trades,
        "long_term_picks": long_term_picks,
        "avoid_list": avoid_list
    }
    
    # 輸出成 index.html 所讀取的 data.json
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(dashboard_data, f, ensure_ascii=False, indent=2)
        
    print("Dashboard 數據已成功更新至 data.json。")

if __name__ == "__main__":
    main()
