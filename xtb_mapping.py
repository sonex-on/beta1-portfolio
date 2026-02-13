# =============================================================================
# xtb_mapping.py — XTB Broker → Yahoo Finance ticker mapping
# Maps XTB-style ticker symbols to valid yfinance symbols
# =============================================================================
import yfinance as yf

# ─── Explicit XTB CFD/ETF/Synthetic → yfinance mapping ─────────────────────
# XTB uses custom names for ETFs, indices, and CFDs that don't exist on Yahoo.
# This dict maps them to the closest real yfinance-tradeable equivalent.
XTB_TO_YFINANCE = {
    # --- S&P 500 ETFs / Indices ---
    "SP500ETF":         "SPY",      # SPDR S&P 500 ETF Trust
    "SP500":            "SPY",
    "US500":            "^GSPC",    # S&P 500 Index (CFD on XTB)
    # --- Sector ETFs ---
    "SP500ITSECTOR":    "XLK",      # Technology Select Sector SPDR
    "SP500FINANCIALS":  "XLF",      # Financial Select Sector SPDR
    "SP500ENERGY":      "XLE",      # Energy Select Sector SPDR
    "SP500HEALTH":      "XLV",      # Health Care Select Sector SPDR
    "SP500INDUSTRIAL":  "XLI",      # Industrial Select Sector SPDR
    "SP500CONSUMER":    "XLY",      # Consumer Discretionary Select Sector SPDR
    "SP500STAPLES":     "XLP",      # Consumer Staples Select Sector SPDR
    "SP500MATERIALS":   "XLB",      # Materials Select Sector SPDR
    "SP500REALESTATE":  "XLRE",     # Real Estate Select Sector SPDR
    "SP500UTILITIES":   "XLU",      # Utilities Select Sector SPDR
    "SP500COMMS":       "XLC",      # Communication Services Select Sector SPDR
    # --- Nasdaq ---
    "NASDAQETF":        "QQQ",      # Invesco QQQ Trust
    "NASDAQ100":        "QQQ",
    "US100":            "^NDX",     # Nasdaq 100 Index
    "USTECH100":        "^NDX",
    # --- Dow Jones ---
    "DOWJONESETF":      "DIA",      # SPDR Dow Jones Industrial Average ETF
    "US30":             "^DJI",     # Dow Jones Index
    # --- European ---
    "DE30":             "^GDAXI",   # DAX Index
    "DE40":             "^GDAXI",
    "UK100":            "^FTSE",    # FTSE 100 Index
    "EU50":             "^STOXX50E",# Euro Stoxx 50
    "FRA40":            "^FCHI",    # CAC 40
    "W20":              "^WIG20",   # WIG 20
    # --- Commodities ---
    "GOLD":             "GC=F",     # Gold Futures
    "SILVER":           "SI=F",     # Silver Futures
    "OIL":              "CL=F",     # Crude Oil Futures
    "OIL.WTI":          "CL=F",
    "NATGAS":           "NG=F",     # Natural Gas Futures
    # --- Crypto CFDs (XTB format) ---
    "BITCOIN":          "BTC-USD",
    "ETHEREUM":         "ETH-USD",
    # --- Popular XTB ETFs (European-listed, UCITS) ---
    "SXR8.DE":          "SXR8.DE",  # iShares Core S&P 500 UCITS (Acc EUR)
    "VUAA.DE":          "VUAA.DE",  # Vanguard S&P 500 UCITS (Acc EUR)
    "QDVE.DE":          "QDVE.DE",  # iShares S&P 500 IT Sector UCITS (Acc EUR)
    "VUSA.UK":          "VUSA.L",   # Vanguard S&P 500 UCITS (Dist GBP) → .L on yfinance
    "IUSA.UK":          "IUSA.L",   # iShares S&P 500 UCITS (Dist GBP)
    "SPY5.UK":          "SPY5.L",   # SPDR S&P 500 UCITS (Dist GBP)
    "EQQQ.UK":          "EQQQ.L",   # Invesco EQQQ NASDAQ-100 UCITS
    "CSPX.UK":          "CSPX.L",   # iShares Core S&P 500 UCITS (Acc USD)
    "IUIT.UK":          "IUIT.L",   # iShares S&P 500 IT Sector UCITS (Acc USD)
    "VWRL.UK":          "VWRL.L",   # Vanguard FTSE All-World UCITS
    "VWCE.DE":          "VWCE.DE",  # Vanguard FTSE All-World UCITS (Acc EUR)
    "IWDA.UK":          "IWDA.L",   # iShares Core MSCI World UCITS
}

# ─── Suffix mapping: XTB exchange suffix → yfinance exchange suffix ────────
XTB_SUFFIX_TO_YF = {
    ".US": "",       # US stocks: AAPL.US → AAPL
    ".UK": ".L",     # UK stocks: BARC.UK → BARC.L (London)
    ".DE": ".DE",    # German stocks: keep as-is
    ".FR": ".PA",    # French stocks: → Paris
    ".NL": ".AS",    # Dutch stocks: → Amsterdam
    ".ES": ".MC",    # Spanish stocks: → Madrid
    ".IT": ".MI",    # Italian stocks: → Milan
    ".PL": ".WA",    # Polish stocks: → Warsaw
    ".SE": ".ST",    # Swedish stocks: → Stockholm
    ".NO": ".OL",    # Norwegian stocks: → Oslo
    ".DK": ".CO",    # Danish stocks: → Copenhagen
    ".FI": ".HE",    # Finnish stocks: → Helsinki
    ".PT": ".LS",    # Portuguese stocks: → Lisbon
    ".AT": ".VI",    # Austrian stocks: → Vienna
    ".IE": ".IR",    # Irish stocks: → Irish Exchange
    ".CH": ".SW",    # Swiss stocks: → Swiss Exchange
    ".HK": ".HK",    # Hong Kong: keep as-is
    ".AU": ".AX",    # Australian stocks: → ASX
    ".JP": ".T",     # Japanese stocks: → Tokyo
}


def resolve_xtb_ticker(ticker: str) -> str:
    """Resolve an XTB-style ticker to a valid yfinance symbol.

    Resolution pipeline:
    1. Check explicit XTB_TO_YFINANCE mapping
    2. Convert suffix using XTB_SUFFIX_TO_YF
    3. Return original ticker if no mapping found
    """
    if not ticker:
        return ticker

    upper = ticker.upper().strip()

    # 1. Explicit mapping (exact match, case-insensitive)
    if upper in XTB_TO_YFINANCE:
        return XTB_TO_YFINANCE[upper]

    # 2. Check suffix mapping
    for xtb_suffix, yf_suffix in XTB_SUFFIX_TO_YF.items():
        if upper.endswith(xtb_suffix):
            base = ticker[:len(ticker) - len(xtb_suffix)]
            return f"{base}{yf_suffix}" if yf_suffix else base

    # 3. No mapping found — return original
    return ticker
