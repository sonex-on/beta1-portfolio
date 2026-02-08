# =============================================================================
# ticker_db.py — Baza tickerów dla beta1 Portfolio Tracker
# US Stocks, GPW, UK, Krypto Top 10
# =============================================================================

# Format: "TICKER — Nazwa" : "ticker_yfinance"

TICKER_DATABASE = {
    # =========================================================================
    # 🪙 KRYPTOWALUTY (Top 10)
    # =========================================================================
    "BTC-USD — Bitcoin": "BTC-USD",
    "ETH-USD — Ethereum": "ETH-USD",
    "BNB-USD — Binance Coin": "BNB-USD",
    "XRP-USD — Ripple": "XRP-USD",
    "ADA-USD — Cardano": "ADA-USD",
    "SOL-USD — Solana": "SOL-USD",
    "DOGE-USD — Dogecoin": "DOGE-USD",
    "DOT-USD — Polkadot": "DOT-USD",
    "AVAX-USD — Avalanche": "AVAX-USD",
    "POL-USD — Polygon (MATIC)": "POL-USD",

    # =========================================================================
    # 🇺🇸 US STOCKS (Top ~60)
    # =========================================================================
    "AAPL — Apple Inc.": "AAPL",
    "MSFT — Microsoft Corp.": "MSFT",
    "GOOGL — Alphabet (Google) Class A": "GOOGL",
    "GOOG — Alphabet (Google) Class C": "GOOG",
    "AMZN — Amazon.com Inc.": "AMZN",
    "NVDA — NVIDIA Corp.": "NVDA",
    "META — Meta Platforms (Facebook)": "META",
    "TSLA — Tesla Inc.": "TSLA",
    "BRK-B — Berkshire Hathaway Class B": "BRK-B",
    "JPM — JPMorgan Chase & Co.": "JPM",
    "V — Visa Inc.": "V",
    "JNJ — Johnson & Johnson": "JNJ",
    "WMT — Walmart Inc.": "WMT",
    "MA — Mastercard Inc.": "MA",
    "PG — Procter & Gamble": "PG",
    "UNH — UnitedHealth Group": "UNH",
    "HD — Home Depot Inc.": "HD",
    "DIS — Walt Disney Co.": "DIS",
    "BAC — Bank of America": "BAC",
    "XOM — Exxon Mobil Corp.": "XOM",
    "KO — Coca-Cola Co.": "KO",
    "PEP — PepsiCo Inc.": "PEP",
    "CSCO — Cisco Systems": "CSCO",
    "AVGO — Broadcom Inc.": "AVGO",
    "COST — Costco Wholesale": "COST",
    "ADBE — Adobe Inc.": "ADBE",
    "CRM — Salesforce Inc.": "CRM",
    "NFLX — Netflix Inc.": "NFLX",
    "AMD — Advanced Micro Devices": "AMD",
    "INTC — Intel Corp.": "INTC",
    "CMCSA — Comcast Corp.": "CMCSA",
    "PFE — Pfizer Inc.": "PFE",
    "TMO — Thermo Fisher Scientific": "TMO",
    "NKE — Nike Inc.": "NKE",
    "ABT — Abbott Laboratories": "ABT",
    "ORCL — Oracle Corp.": "ORCL",
    "ACN — Accenture plc": "ACN",
    "MRK — Merck & Co.": "MRK",
    "LLY — Eli Lilly & Co.": "LLY",
    "T — AT&T Inc.": "T",
    "VZ — Verizon Communications": "VZ",
    "DHR — Danaher Corp.": "DHR",
    "QCOM — Qualcomm Inc.": "QCOM",
    "TXN — Texas Instruments": "TXN",
    "UPS — United Parcel Service": "UPS",
    "PM — Philip Morris International": "PM",
    "NEE — NextEra Energy": "NEE",
    "SPGI — S&P Global Inc.": "SPGI",
    "RTX — RTX Corp. (Raytheon)": "RTX",
    "LOW — Lowe's Companies": "LOW",
    "HON — Honeywell International": "HON",
    "MS — Morgan Stanley": "MS",
    "GS — Goldman Sachs Group": "GS",
    "BLK — BlackRock Inc.": "BLK",
    "SBUX — Starbucks Corp.": "SBUX",
    "CAT — Caterpillar Inc.": "CAT",
    "BA — Boeing Co.": "BA",
    "DE — Deere & Company": "DE",
    "ISRG — Intuitive Surgical": "ISRG",
    "MMM — 3M Company": "MMM",
    "GE — General Electric": "GE",
    "AMT — American Tower Corp.": "AMT",
    "PYPL — PayPal Holdings": "PYPL",
    "SQ — Block Inc. (Square)": "SQ",
    "COIN — Coinbase Global": "COIN",
    "PLTR — Palantir Technologies": "PLTR",
    "SOFI — SoFi Technologies": "SOFI",
    "UBER — Uber Technologies": "UBER",
    "SNAP — Snap Inc.": "SNAP",
    "RBLX — Roblox Corp.": "RBLX",
    "ABNB — Airbnb Inc.": "ABNB",
    "RIVN — Rivian Automotive": "RIVN",
    "LCID — Lucid Group": "LCID",
    "NIO — NIO Inc.": "NIO",
    "MSTR — MicroStrategy": "MSTR",
    "GME — GameStop Corp.": "GME",
    "AMC — AMC Entertainment": "AMC",
    "SPY — SPDR S&P 500 ETF": "SPY",
    "QQQ — Invesco QQQ (Nasdaq 100)": "QQQ",
    "VOO — Vanguard S&P 500 ETF": "VOO",

    # =========================================================================
    # 🇵🇱 GPW — Giełda Papierów Wartościowych
    # =========================================================================
    "CDR.WA — CD Projekt": "CDR.WA",
    "PKN.WA — PKN Orlen": "PKN.WA",
    "PZU.WA — PZU SA": "PZU.WA",
    "KGH.WA — KGHM Polska Miedź": "KGH.WA",
    "PEO.WA — Pekao SA": "PEO.WA",
    "PKO.WA — PKO Bank Polski": "PKO.WA",
    "LPP.WA — LPP SA": "LPP.WA",
    "DNP.WA — Dino Polska": "DNP.WA",
    "ALE.WA — Allegro": "ALE.WA",
    "SPL.WA — Santander Bank Polska": "SPL.WA",
    "MBK.WA — mBank SA": "MBK.WA",
    "CPS.WA — Cyfrowy Polsat": "CPS.WA",
    "JSW.WA — JSW SA": "JSW.WA",
    "TPE.WA — Tauron Polska Energia": "TPE.WA",
    "PGE.WA — PGE SA": "PGE.WA",
    "OPL.WA — Orange Polska": "OPL.WA",
    "PCO.WA — Pepco Group": "PCO.WA",
    "KRU.WA — Kruk SA": "KRU.WA",
    "11B.WA — 11 bit studios": "11B.WA",
    "TEN.WA — Ten Square Games": "TEN.WA",
    "BDX.WA — Budimex SA": "BDX.WA",
    "ATC.WA — Arctic Paper": "ATC.WA",
    "ASB.WA — Asseco Poland": "ASB.WA",
    "CCC.WA — CCC SA": "CCC.WA",
    "AMC.WA — Amica SA": "AMC.WA",
    "ENA.WA — Enea SA": "ENA.WA",
    "LTS.WA — Lotus Bakeries (GPW)": "LTS.WA",
    "MIL.WA — Bank Millennium": "MIL.WA",
    "ING.WA — ING Bank Śląski": "ING.WA",
    "ZEP.WA — Żywiec SA": "ZEP.WA",

    # =========================================================================
    # 🇬🇧 UK STOCKS (London Stock Exchange)
    # =========================================================================
    "VOD.L — Vodafone Group": "VOD.L",
    "BARC.L — Barclays plc": "BARC.L",
    "HSBA.L — HSBC Holdings": "HSBA.L",
    "BP.L — BP plc": "BP.L",
    "SHEL.L — Shell plc": "SHEL.L",
    "GSK.L — GSK plc": "GSK.L",
    "AZN.L — AstraZeneca": "AZN.L",
    "ULVR.L — Unilever plc": "ULVR.L",
    "RIO.L — Rio Tinto": "RIO.L",
    "LLOY.L — Lloyds Banking Group": "LLOY.L",
    "GLEN.L — Glencore plc": "GLEN.L",
    "BT-A.L — BT Group": "BT-A.L",
    "NG.L — National Grid": "NG.L",
    "LSEG.L — London Stock Exchange Group": "LSEG.L",
    "RKT.L — Reckitt Benckiser": "RKT.L",
    "REL.L — RELX plc": "REL.L",
    "CPG.L — Compass Group": "CPG.L",
    "DGE.L — Diageo plc": "DGE.L",
    "BA.L — BAE Systems": "BA.L",
    "RR.L — Rolls-Royce Holdings": "RR.L",
}


def szukaj_tickery(zapytanie: str, limit: int = 15) -> list:
    """
    Wyszukuje tickery na podstawie zapytania (ticker lub nazwa spółki).
    Zwraca listę pasujących kluczy z TICKER_DATABASE.
    """
    if not zapytanie or len(zapytanie) < 1:
        return list(TICKER_DATABASE.keys())[:limit]

    zapytanie = zapytanie.upper().strip()
    wyniki = []

    # Najpierw: dokładne dopasowanie tickera
    for klucz, ticker in TICKER_DATABASE.items():
        if ticker.upper() == zapytanie:
            wyniki.insert(0, klucz)

    # Potem: ticker zaczyna się od zapytania
    for klucz, ticker in TICKER_DATABASE.items():
        if ticker.upper().startswith(zapytanie) and klucz not in wyniki:
            wyniki.append(klucz)

    # Na końcu: nazwa zawiera zapytanie
    for klucz in TICKER_DATABASE:
        if zapytanie in klucz.upper() and klucz not in wyniki:
            wyniki.append(klucz)

    return wyniki[:limit]
