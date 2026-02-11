# =============================================================================
# BETA1 — Portfolio Tracker v2 (Cloud Edition)
# Streamlit + Firebase Auth + Firestore + yfinance + Plotly
# Waluta: USD ($) | Rynki: US, GPW, UK, Krypto Top 10
# =============================================================================

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import os
import requests

from firebase_config import (
    inicjalizuj_firebase, zarejestruj_uzytkownika, zaloguj_uzytkownika,
    pobierz_portfele, stworz_portfel, usun_portfel,
    pobierz_transakcje, dodaj_transakcje, usun_transakcje, zapisz_profil,
    odswiez_token, wyslij_weryfikacje_email, sprawdz_weryfikacje, wyslij_reset_hasla,
)
from ticker_db import TICKER_DATABASE, szukaj_tickery
from translations import t
from statistics import (
    oblicz_statystyki, oblicz_drawdown_serie,
    oblicz_growth_serie, oblicz_profit_serie,
)
import re
import random
import numpy as np
import base64

# ─── Benchmark helper ─────────────────────────────────────────────────────────
_BENCHMARKS = {
    "S&P 500": "^GSPC",
    "WIG20": "WIG20.WA",
}

@st.cache_data(ttl=3600, show_spinner=False)
def pobierz_benchmark_growth(ticker: str, start_date, end_date) -> pd.Series:
    """Fetch benchmark index and return cumulative growth % aligned to date range."""
    try:
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if df.empty or len(df) < 2:
            return pd.Series(dtype=float)
        close = df["Close"].squeeze()
        growth = ((close / close.iloc[0]) - 1) * 100
        growth.index = growth.index.tz_localize(None)
        return growth
    except Exception:
        return pd.Series(dtype=float)

@st.cache_data(ttl=86400, show_spinner=False)
def pobierz_sektor(ticker: str) -> str:
    """Fetch sector for a ticker from yfinance."""
    try:
        info = yf.Ticker(ticker).info
        return info.get("sector", "Unknown")
    except Exception:
        return "Unknown"

@st.cache_data(ttl=3600, show_spinner=False)
def pobierz_korelacje(tickers: list, days: int = 90) -> pd.DataFrame:
    """Fetch correlation matrix for a list of tickers."""
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        data = yf.download(tickers, start=start, end=end, progress=False)["Close"]
        if isinstance(data, pd.Series):
            data = data.to_frame()
        return data.pct_change().dropna().corr()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=86400, show_spinner=False)
def pobierz_dywidendy(ticker: str) -> dict:
    """Fetch dividend info for a ticker."""
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        divs = tk.dividends
        last_div = f"${divs.iloc[-1]:.4f}" if len(divs) > 0 else "—"
        return {
            "yield": info.get("dividendYield", 0) or 0,
            "last": last_div,
        }
    except Exception:
        return {"yield": 0, "last": "—"}

@st.cache_data(ttl=86400, show_spinner=False)
def pobierz_kalendarz(ticker: str) -> list:
    """Fetch upcoming earnings/events for a ticker."""
    try:
        tk = yf.Ticker(ticker)
        cal = tk.calendar
        events = []
        if cal is not None and not cal.empty:
            for col in cal.columns:
                for idx in cal.index:
                    val = cal.loc[idx, col]
                    if pd.notna(val):
                        events.append({"date": str(col), "event": str(idx), "value": str(val)})
        return events
    except Exception:
        return []

from ocr_reader import extract_transactions_from_image
from logo_fetcher import get_logo_html

# =============================================================================
# STAŁE
# =============================================================================
APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(APP_DIR, "assets", "logo.jpg")

# Tickery — pełna baza w ticker_db.py

PALETY_KOLOROW = {
    "Oceanic": ["#0077B6", "#00B4D8", "#90E0EF", "#CAF0F8", "#023E8A", "#03045E"],
    "Sunset": ["#FF6B6B", "#FFA07A", "#FFD93D", "#6BCB77", "#4D96FF", "#FF5E78"],
    "Neon": ["#00F5FF", "#FF00E4", "#FFE600", "#00FF87", "#FF3131", "#7B2FFF"],
    "Forest": ["#2D6A4F", "#40916C", "#52B788", "#74C69D", "#95D5B2", "#B7E4C7"],
    "Royal": ["#7400B8", "#6930C3", "#5E60CE", "#5390D9", "#4EA8DE", "#48BFE3"],
}

# --- Interactive Chart Configuration (TradingView-style) ---
CHART_CONFIG = {
    "scrollZoom": True,
    "displayModeBar": "hover",
    "displaylogo": False,
    "doubleClick": "reset+autosize",
    "modeBarButtonsToRemove": ["select2d", "lasso2d"],
    "modeBarButtonsToAdd": ["drawline", "eraseshape"],
    "modeBarStyle": {"bgcolor": "rgba(19,23,34,0.8)", "color": "#787B86", "activecolor": "#2962FF"},
}

# --- Crypto detection & BloFin API ---
CRYPTO_BASE = {"BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK", "MATIC",
               "SHIB", "LTC", "UNI", "ATOM", "FIL", "APT", "ARB", "OP", "SUI", "SEI",
               "NEAR", "FTM", "INJ", "TIA", "PEPE", "WIF", "BONK", "RENDER", "TRX",
               "TON", "BNB", "AAVE", "MKR", "CRV", "SUSHI"}

def is_crypto(ticker: str) -> bool:
    """Auto-detect if ticker is a cryptocurrency."""
    t = ticker.upper()
    if any(t.endswith(s) for s in ("-USD", "-USDT", "-EUR", "-GBP")):
        return True
    base = t.split("-")[0].split("/")[0]
    return base in CRYPTO_BASE

def ticker_to_blofin(ticker: str) -> str:
    """Convert user ticker to BloFin instId (e.g. 'BTC-USD' → 'BTC-USDT')."""
    t = ticker.upper().replace("/", "-")
    for suffix in ("-USD", "-EUR", "-GBP"):
        if t.endswith(suffix):
            return t.replace(suffix, "-USDT")
    if "-" not in t:
        return t + "-USDT"
    return t

BLOFIN_BAR_MAP = {
    "15m": "15m", "30m": "30m", "1h": "1H", "2h": "2H", "4h": "4H",
    "12h": "12H", "1D": "1D", "3D": "3D", "5D": "1D",  # 5D not native, use 1D + resample
    "1W": "1W", "1M": "1M",
}

@st.cache_data(ttl=30)  # cache 30s for near-real-time
def fetch_blofin_candles(inst_id: str, bar: str = "1D", limit: int = 300) -> pd.DataFrame:
    """Fetch OHLCV candlestick data from BloFin public API with pagination for deep history."""
    import time
    url = "https://openapi.blofin.com/api/v1/market/candles"
    all_rows = []
    remaining = limit
    after_ts = None
    max_pages = 6  # max 6 pages = up to 8640 candles

    try:
        for _ in range(max_pages):
            if remaining <= 0:
                break
            batch = min(remaining, 1440)
            params = {"instId": inst_id, "bar": bar, "limit": batch}
            if after_ts:
                params["after"] = str(after_ts)
            r = requests.get(url, params=params, timeout=10)
            data = r.json()
            if data.get("code") != "0" or not data.get("data"):
                break
            rows = data["data"]
            all_rows.extend(rows)
            remaining -= len(rows)
            # BloFin returns newest first; last row = oldest — use 'after' to go further back
            after_ts = int(float(rows[-1][0]))
            if len(rows) < batch:
                break  # no more data available
            time.sleep(0.1)  # rate limit courtesy

        if not all_rows:
            return pd.DataFrame()

        df = pd.DataFrame(all_rows, columns=["ts", "Open", "High", "Low", "Close",
                                               "Volume", "VolCcy", "VolCcyQuote", "Confirm"])
        df["ts"] = pd.to_datetime(df["ts"].astype(float), unit="ms")
        df = df.drop_duplicates(subset=["ts"]).set_index("ts").sort_index()
        for c in ["Open", "High", "Low", "Close", "Volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        return df
    except Exception:
        return pd.DataFrame()

# =============================================================================
# MOTYWY I CSS
# =============================================================================
def zastosuj_motyw(ciemny: bool, paleta_nazwa: str):
    """Aplikuje CSS motywu + paletę kolorów. DESIGNER agent v2 — trading platform style."""
    paleta = PALETY_KOLOROW.get(paleta_nazwa, PALETY_KOLOROW["Oceanic"])
    k1, k2 = paleta[0], paleta[1]
    if ciemny:
        tlo, tlo_k, tekst, ramka, tlo_sb = "#0a0e17", "#111827", "#F1F5F9", "#1e293b", "#0f1520"
        card_bg = "rgba(17,24,39,0.85)"
        card_border = "rgba(255,255,255,0.06)"
        glass = "backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);"
        stat_bg = "linear-gradient(135deg, #1a1f2e 0%, #0f1420 100%)"
        stat_border = "rgba(255,255,255,0.05)"
        stat_row_hover = "rgba(255,255,255,0.03)"
        tab_bg = "rgba(255,255,255,0.04)"
        tab_active = k1
        tab_text = "#94a3b8"
        tab_active_text = "#ffffff"
    else:
        tlo, tlo_k, tekst, ramka, tlo_sb = "#f8fafc", "#ffffff", "#0f172a", "#e2e8f0", "#f1f5f9"
        card_bg = "rgba(255,255,255,0.9)"
        card_border = "rgba(0,0,0,0.06)"
        glass = "backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);"
        stat_bg = "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)"
        stat_border = "rgba(0,0,0,0.08)"
        stat_row_hover = "rgba(0,0,0,0.02)"
        tab_bg = "rgba(0,0,0,0.04)"
        tab_active = k1
        tab_text = "#64748b"
        tab_active_text = "#ffffff"

    st.markdown(f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
    * {{ font-family: 'Inter', -apple-system, sans-serif !important; }}
    .stApp {{ background: {tlo}; color: {tekst}; }}
    section[data-testid="stSidebar"] {{ background: {tlo_sb}; border-right: 1px solid {card_border}; }}

    /* --- Metric Cards --- */
    .metric-card {{
        background: {card_bg}; {glass}
        border: 1px solid {card_border}; border-radius: 16px;
        padding: 18px 20px; text-align: center;
        box-shadow: 0 4px 24px rgba(0,0,0,0.12);
        transition: transform 0.25s cubic-bezier(.4,0,.2,1), box-shadow 0.25s;
    }}
    .metric-card:hover {{ transform: translateY(-3px); box-shadow: 0 12px 40px rgba(0,0,0,0.2); }}
    .metric-card .value {{ font-size: 1.7rem; font-weight: 800; color: {k1}; margin: 6px 0 3px; letter-spacing: -0.02em; }}
    .metric-card .label {{ font-size: 0.7rem; color: {tekst}99; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600; }}
    .metric-card .sub {{ font-size: 0.8rem; margin-top: 2px; }}
    .delta-positive {{ color: #10b981; }} .delta-negative {{ color: #ef4444; }}

    /* --- Typography --- */
    .app-title {{ text-align:center; font-size:2rem; font-weight:900; letter-spacing:-0.03em;
        background: linear-gradient(135deg, {k1}, {k2});
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom:2px; }}
    .app-subtitle {{ text-align:center; font-size:0.8rem; color:{tekst}66; margin-bottom:24px; font-weight:500; }}
    .section-header {{ font-size:1.05rem; font-weight:700; color:{k1};
        border-left:3px solid {k1}; padding-left:12px; margin:28px 0 12px; }}
    .loss-badge {{ display:inline-block; background:rgba(239,68,68,0.12); color:#ef4444;
        padding:3px 10px; border-radius:8px; font-size:0.75rem; font-weight:600; margin-top:4px; }}

    /* --- Statistics Table (Trading Platform Style) --- */
    .stat-table {{
        background: {stat_bg};
        border: 1px solid {stat_border};
        border-radius: 12px;
        padding: 20px 24px;
        margin: 16px 0;
    }}
    .stat-table-title {{
        font-size: 0.85rem; font-weight: 700; color: {tekst};
        letter-spacing: 0.5px; margin-bottom: 14px;
    }}
    .stat-row {{
        display: flex; justify-content: space-between; align-items: center;
        padding: 7px 0; border-bottom: 1px solid {stat_border};
        transition: background 0.15s;
    }}
    .stat-row:hover {{ background: {stat_row_hover}; margin: 0 -8px; padding: 7px 8px; border-radius: 6px; }}
    .stat-row:last-child {{ border-bottom: none; }}
    .stat-label {{ font-size: 0.82rem; color: {tab_text}; font-weight: 500; }}
    .stat-val {{ font-size: 0.82rem; font-weight: 700; }}
    .stat-val.positive {{ color: #10b981; }}
    .stat-val.negative {{ color: #ef4444; }}
    .stat-val.neutral {{ color: {tekst}; }}

    /* --- NEW Badge --- */
    .new-badge {{
        display: inline-block;
        background: linear-gradient(135deg, #10b981, #06d6a0);
        color: #fff; font-size: 0.6rem; font-weight: 800;
        padding: 2px 7px; border-radius: 6px;
        letter-spacing: 0.8px; text-transform: uppercase;
        margin-left: 6px; vertical-align: middle;
    }}

    /* --- OCR Import Section --- */
    .ocr-section {{
        background: {stat_bg};
        border: 1px dashed {k1}66;
        border-radius: 12px;
        padding: 14px;
        margin: 8px 0;
        transition: border-color 0.3s;
    }}
    .ocr-section:hover {{ border-color: {k1}; }}
    .ocr-badge {{
        display: inline-block;
        background: linear-gradient(135deg, {k1}, {k2});
        color: #fff; font-size: 0.55rem; font-weight: 800;
        padding: 2px 6px; border-radius: 5px;
        letter-spacing: 0.5px; text-transform: uppercase;
        margin-left: 4px; vertical-align: middle;
    }}
    .ocr-result-header {{
        font-size: 0.82rem; font-weight: 700;
        color: #10b981; margin: 8px 0 4px;
    }}
    .logo-ticker {{
        display: inline-flex; align-items: center;
    }}

    /* --- Streamlit Tab Overrides --- */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px; background: {tab_bg}; border-radius: 12px; padding: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 8px; padding: 8px 18px;
        color: {tab_text}; font-weight: 600; font-size: 0.85rem;
        background: transparent; border: none;
        transition: all 0.2s ease;
    }}
    .stTabs [data-baseweb="tab"]:hover {{ background: rgba(255,255,255,0.06); color: {tekst}; }}
    .stTabs [aria-selected="true"] {{
        background: {tab_active} !important; color: {tab_active_text} !important;
        box-shadow: 0 2px 12px {k1}40;
    }}
    .stTabs [data-baseweb="tab-border"] {{ display: none; }}
    .stTabs [data-baseweb="tab-highlight"] {{ display: none; }}

    /* --- Chart Containers — Smooth Transitions --- */
    .js-plotly-plot {{ transition: all 0.3s cubic-bezier(.4,0,.2,1); }}
    .js-plotly-plot .modebar-container {{
        opacity: 0 !important;
        transition: opacity 0.35s ease !important;
    }}
    .js-plotly-plot:hover .modebar-container {{
        opacity: 1 !important;
    }}
    .js-plotly-plot .modebar-btn {{
        font-size: 16px !important;
    }}
    [data-testid="stPlotlyChart"] {{
        min-height: 50vh;
        transition: height 0.3s ease;
    }}

    /* --- Hide Sidebar --- */
    section[data-testid="stSidebar"] {{ display: none !important; }}
    [data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}
    button[data-testid="stSidebarNavToggle"] {{ display: none !important; }}

    /* --- Top Navbar --- */
    .navbar-row {{
        background: {card_bg}; {glass}
        border: 1px solid {card_border};
        border-radius: 14px;
        padding: 10px 20px;
        margin-bottom: 12px;
        display: flex; align-items: center;
    }}
    </style>""", unsafe_allow_html=True)

# =============================================================================
# WALIDACJA
# =============================================================================
def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Konwertuje hex (#RRGGBB) na rgba() format dla Plotly."""
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def waliduj_ticker(ticker: str) -> str:
    oczyszczony = "".join(c for c in ticker.strip().upper() if c.isalnum() or c in ".-")
    return oczyszczony if 1 <= len(oczyszczony) <= 20 else ""

def waliduj_liczbe(wartosc, min_val=0.0001) -> float:
    try:
        w = float(wartosc)
        return w if w >= min_val else 0.0
    except (ValueError, TypeError):
        return 0.0

# --- SANITIZATION & VALIDATION ---
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
_DANGER_PATTERNS = re.compile(r'<[^>]*>|javascript:|on\w+=|\'|\"--|\/\*|\*\/|;\s*(DROP|DELETE|INSERT|UPDATE|ALTER|EXEC)', re.IGNORECASE)

def sanitize_input(text: str, max_len: int = 200) -> str:
    """Czyści input: usuwa HTML tagi, niebezpieczne wzorce, ogranicza długość."""
    if not isinstance(text, str):
        return ""
    text = text.strip()[:max_len]
    text = _DANGER_PATTERNS.sub('', text)
    return text

def validate_email(email: str) -> bool:
    """Sprawdza poprawność formatu email."""
    return bool(_EMAIL_RE.match(email.strip())) if email else False

def _generate_captcha():
    """Generuje prostą zagadkę matematyczną."""
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    op = random.choice(['+', '-', '×'])
    if op == '+':
        answer = a + b
    elif op == '-':
        a, b = max(a, b), min(a, b)  # wynik zawsze >= 0
        answer = a - b
    else:
        a, b = random.randint(1, 10), random.randint(1, 10)
        answer = a * b
    return f"{a} {op} {b} = ?", answer

MAX_LOGIN_ATTEMPTS = 5

# =============================================================================
# YFINANCE — Pobieranie danych (Agent 2)
# =============================================================================
@st.cache_data(ttl=900, show_spinner=False)
def pobierz_aktualna_cene(ticker: str) -> dict:
    """Pobiera aktualną cenę z yfinance. Cache 15 min."""
    try:
        akcja = yf.Ticker(ticker)
        info = akcja.info
        cena = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        if not cena:
            hist = akcja.history(period="2d")
            if not hist.empty:
                cena = hist["Close"].iloc[-1]
            else:
                return {"error": f"Nie znaleziono danych: {ticker}"}
        hist_5d = akcja.history(period="5d")
        zmiennosc = 0.0
        if len(hist_5d) >= 2:
            zmiennosc = ((hist_5d["Close"].iloc[-1] - hist_5d["Close"].iloc[-2]) / hist_5d["Close"].iloc[-2]) * 100
        return {"cena": float(cena), "nazwa": info.get("shortName", ticker),
                "zmiennosc_dzienna": round(zmiennosc, 2), "error": None}
    except Exception as e:
        return {"error": f"Błąd: {str(e)[:100]}"}

@st.cache_data(ttl=3600, show_spinner=False)
def pobierz_historie(ticker: str, data_od: str) -> pd.DataFrame:
    """Pobiera historyczne dane zamknięcia."""
    try:
        hist = yf.Ticker(ticker).history(start=data_od)
        if hist.empty: return pd.DataFrame()
        hist = hist[["Close"]].reset_index()
        hist.columns = ["Data", "Zamkniecie"]
        hist["Data"] = pd.to_datetime(hist["Data"]).dt.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()

# =============================================================================
# OBLICZENIA PORTFELA
# =============================================================================
def oblicz_portfel(transakcje: list) -> pd.DataFrame:
    """Oblicza podsumowanie portfela z listy transakcji."""
    if not transakcje: return pd.DataFrame()
    df = pd.DataFrame(transakcje)
    wyniki = []
    for ticker in df["ticker"].unique():
        df_t = df[df["ticker"] == ticker]
        ilosc_netto, koszt = 0.0, 0.0
        for _, row in df_t.iterrows():
            if row["typ"] == "Kupno":
                koszt += float(row["ilosc"]) * float(row["cena_zakupu"])
                ilosc_netto += float(row["ilosc"])
            else:
                if ilosc_netto > 0:
                    sr = koszt / ilosc_netto
                    sprzedaz = min(float(row["ilosc"]), ilosc_netto)
                    koszt -= sr * sprzedaz
                    ilosc_netto -= sprzedaz
        if ilosc_netto <= 0: continue
        srednia_cena = koszt / ilosc_netto if ilosc_netto > 0 else 0
        dane = pobierz_aktualna_cene(ticker)
        cena_akt = dane["cena"] if not dane.get("error") else srednia_cena
        zmiennosc = dane.get("zmiennosc_dzienna", 0) if not dane.get("error") else 0
        nazwa = dane.get("nazwa", ticker) if not dane.get("error") else ticker
        wartosc = ilosc_netto * cena_akt
        zysk = wartosc - koszt
        roi = ((cena_akt - srednia_cena) / srednia_cena * 100) if srednia_cena > 0 else 0
        wyniki.append({"Ticker": ticker, "Nazwa": nazwa, "Ilość": round(ilosc_netto, 4),
            "Śr. Cena Zakupu ($)": round(srednia_cena, 2), "Cena Bieżąca ($)": round(cena_akt, 2),
            "Wartość ($)": round(wartosc, 2), "Zysk/Strata ($)": round(zysk, 2),
            "ROI (%)": round(roi, 2), "Zmienność (%)": zmiennosc})
    return pd.DataFrame(wyniki) if wyniki else pd.DataFrame()

def oblicz_historie_portfela(transakcje: list) -> pd.DataFrame:
    """Historia wartości portfela w czasie."""
    if not transakcje: return pd.DataFrame()
    df = pd.DataFrame(transakcje)
    df["data"] = pd.to_datetime(df["data"])
    data_start = df["data"].min().strftime("%Y-%m-%d")
    historie = {}
    for ticker in df["ticker"].unique():
        h = pobierz_historie(ticker, data_start)
        if not h.empty: historie[ticker] = h.set_index("Data")["Zamkniecie"]
    if not historie: return pd.DataFrame()
    df_hist = pd.DataFrame(historie).ffill().bfill()
    wartosci = []
    for data_idx in df_hist.index:
        wartosc_dnia = 0.0
        for ticker in df["ticker"].unique():
            if ticker not in df_hist.columns: continue
            trans = df[(df["ticker"] == ticker) & (df["data"] <= data_idx)]
            il = sum(float(r["ilosc"]) if r["typ"] == "Kupno" else -float(r["ilosc"]) for _, r in trans.iterrows())
            wartosc_dnia += max(il, 0) * df_hist.loc[data_idx, ticker]
        wartosci.append({"Data": data_idx, "Wartość Portfela ($)": round(wartosc_dnia, 2)})
    return pd.DataFrame(wartosci)

def oblicz_roi_portfela(transakcje: list) -> pd.DataFrame:
    """Oblicza dzienną stopę zwrotu (ROI%) całego portfela w czasie."""
    if not transakcje: return pd.DataFrame()
    df = pd.DataFrame(transakcje)
    df["data"] = pd.to_datetime(df["data"])
    df["ilosc"] = df["ilosc"].astype(float)
    df["cena_zakupu"] = df["cena_zakupu"].astype(float)
    data_start = df["data"].min().strftime("%Y-%m-%d")
    # Pobierz historię cen
    historie = {}
    for ticker in df["ticker"].unique():
        h = pobierz_historie(ticker, data_start)
        if not h.empty: historie[ticker] = h.set_index("Data")["Zamkniecie"]
    if not historie: return pd.DataFrame()
    df_hist = pd.DataFrame(historie).ffill().bfill()
    wyniki = []
    for data_idx in df_hist.index:
        wartosc_rynkowa = 0.0
        kapital_zainwestowany = 0.0
        for ticker in df["ticker"].unique():
            if ticker not in df_hist.columns: continue
            trans = df[(df["ticker"] == ticker) & (df["data"] <= data_idx)]
            ilosc_netto = 0.0
            koszt_netto = 0.0
            for _, r in trans.iterrows():
                if r["typ"] == "Kupno":
                    ilosc_netto += r["ilosc"]
                    koszt_netto += r["ilosc"] * r["cena_zakupu"]
                else:
                    if ilosc_netto > 0:
                        sr = koszt_netto / ilosc_netto
                        sprzedaz = min(r["ilosc"], ilosc_netto)
                        koszt_netto -= sr * sprzedaz
                        ilosc_netto -= sprzedaz
            wartosc_rynkowa += max(ilosc_netto, 0) * df_hist.loc[data_idx, ticker]
            kapital_zainwestowany += max(koszt_netto, 0)
        roi = ((wartosc_rynkowa - kapital_zainwestowany) / kapital_zainwestowany * 100) if kapital_zainwestowany > 0 else 0
        wyniki.append({"Data": data_idx, "ROI (%)": round(roi, 2), "Wartość ($)": round(wartosc_rynkowa, 2), "Kapitał ($)": round(kapital_zainwestowany, 2)})
    return pd.DataFrame(wyniki)

# =============================================================================
# EKRAN LOGOWANIA / REJESTRACJI
# =============================================================================
def ekran_autentykacji():
    """Wyświetla formularz logowania lub rejestracji. Zwraca True jeśli zalogowany."""
    if st.session_state.get("zalogowany"):
        return True

    # Język — inicjalizacja
    if "lang" not in st.session_state:
        st.session_state.lang = "pl"
    # Rate limiting state
    if "_login_attempts" not in st.session_state:
        st.session_state._login_attempts = {}  # {email: count}
    # CAPTCHA state
    if "_captcha_q" not in st.session_state:
        q, a = _generate_captcha()
        st.session_state._captcha_q = q
        st.session_state._captcha_a = a


    zastosuj_motyw(True, "Oceanic")

    # Logo — centrowane
    if os.path.exists(LOGO_PATH):
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            st.image(LOGO_PATH, width=120)

    st.markdown('<p class="app-title">Portfel inwestycyjny</p>', unsafe_allow_html=True)

    L = st.session_state.lang
    st.markdown(f'<p class="app-subtitle">{t("auth_subtitle", L)}</p>', unsafe_allow_html=True)

    # Wybór języka
    lang_options = {"🇵🇱 Polski": "pl", "🇬🇧 English": "en"}
    lang_labels = list(lang_options.keys())
    current_idx = list(lang_options.values()).index(L) if L in lang_options.values() else 0
    wybrany_jezyk = st.radio(t("language", L), lang_labels, index=current_idx, horizontal=True)
    new_lang = lang_options[wybrany_jezyk]
    if new_lang != st.session_state.lang:
        st.session_state.lang = new_lang
        st.rerun()
    L = st.session_state.lang

    # Tryb — radio
    tryb = st.radio(t("auth_select", L), [t("auth_login", L), t("auth_register", L)], horizontal=True, label_visibility="collapsed")

    # === LOGOWANIE ===
    if tryb == t("auth_login", L):
        with st.form("login_form"):
            email = st.text_input(t("email", L), placeholder="your@email.com")
            haslo = st.text_input(t("password", L), type="password")
            zapamietaj = st.checkbox(t("remember_me", L))
            zaloguj = st.form_submit_button(t("login_btn", L), use_container_width=True)

            if zaloguj:
                email_clean = sanitize_input(email.strip().lower(), 100)

                # Email format
                if not validate_email(email_clean):
                    st.error(t("invalid_email_format", L)); st.stop()

                if not email_clean or not haslo:
                    st.error(t("fill_all", L)); st.stop()

                # Rate limiting check
                attempts = st.session_state._login_attempts.get(email_clean, 0)
                if attempts >= MAX_LOGIN_ATTEMPTS:
                    st.error(t("account_locked", L))
                    # Show password reset button
                    st.stop()

                with st.spinner(t("logging_in", L)):
                    wynik = zaloguj_uzytkownika(email_clean, haslo)

                if wynik.get("error"):
                    # Increment attempts
                    st.session_state._login_attempts[email_clean] = attempts + 1
                    remaining = MAX_LOGIN_ATTEMPTS - attempts - 1
                    if remaining > 0:
                        st.error(f"❌ {wynik['error']} ({t('attempts_left', L)}: {remaining})")
                    else:
                        st.error(t("account_locked", L))
                    # Regenerate CAPTCHA
                    q, a = _generate_captcha()
                    st.session_state._captcha_q, st.session_state._captcha_a = q, a
                else:
                    # Check email verification (soft warning, don't block)
                    if not sprawdz_weryfikacje(wynik["id_token"]):
                        st.session_state._unverified_token = wynik["id_token"]

                    # Success — allow login regardless of verification status
                    st.session_state._login_attempts[email_clean] = 0
                    st.session_state.zalogowany = True
                    st.session_state.uid = wynik["uid"]
                    st.session_state.email = wynik["email"]
                    st.session_state.id_token = wynik["id_token"]
                    st.success(t("logged_in", L))
                    st.rerun()

        # Password reset button (outside form)
        locked_emails = [e for e, c in st.session_state._login_attempts.items() if c >= MAX_LOGIN_ATTEMPTS]
        if locked_emails:
            st.markdown("---")
            reset_email = st.text_input("📧 Email", value=locked_emails[0], key="reset_email")
            if st.button(t("reset_password", L), key="btn_reset"):
                if validate_email(reset_email):
                    wyslij_reset_hasla(reset_email)
                    st.success(f"{t('reset_sent', L)} {reset_email}")
                    st.session_state._login_attempts[reset_email] = 0

        # Resend verification button
        if st.session_state.get("_unverified_token"):
            if st.button(t("resend_verification", L), key="btn_resend"):
                res = wyslij_weryfikacje_email(st.session_state._unverified_token)
                if res.get("error"):
                    st.error(f"❌ {res['error']}")
                else:
                    st.success(t("verification_sent", L))

    # === REJESTRACJA ===
    else:
        # CAPTCHA — only for registration
        st.markdown(f'**{t("captcha_label", L)}:** `{st.session_state._captcha_q}`')
        captcha_answer = st.text_input(t("captcha_placeholder", L), key="captcha_input", max_chars=6)

        with st.form("register_form"):
            reg_email = st.text_input(t("email", L), placeholder="your@email.com")
            reg_haslo = st.text_input(t("password_min", L), type="password")
            reg_haslo2 = st.text_input(t("password_repeat", L), type="password")
            zarejestruj = st.form_submit_button(t("register_btn", L), use_container_width=True)

            if zarejestruj:
                reg_email_clean = sanitize_input(reg_email.strip().lower(), 100)

                # CAPTCHA check
                try:
                    if int(captcha_answer) != st.session_state._captcha_a:
                        st.error(t("captcha_wrong", L))
                        q, a = _generate_captcha()
                        st.session_state._captcha_q, st.session_state._captcha_a = q, a
                        st.stop()
                except (ValueError, TypeError):
                    st.error(t("captcha_wrong", L))
                    st.stop()

                # Validations
                if not validate_email(reg_email_clean):
                    st.error(t("invalid_email_format", L)); st.stop()
                if not reg_email_clean or not reg_haslo:
                    st.error(t("fill_all", L))
                elif reg_haslo != reg_haslo2:
                    st.error(t("passwords_mismatch", L))
                elif len(reg_haslo) < 6:
                    st.error(t("password_too_short", L))
                else:
                    with st.spinner(t("registering", L)):
                        wynik = zarejestruj_uzytkownika(reg_email_clean, reg_haslo)
                    if wynik.get("error"):
                        st.error(f"❌ {wynik['error']}")
                    else:
                        db = inicjalizuj_firebase()
                        zapisz_profil(db, wynik["uid"], wynik["email"])
                        # Send email verification
                        ver_result = wyslij_weryfikacje_email(wynik["id_token"])
                        if ver_result.get("error"):
                            st.error(f"❌ Weryfikacja email: {ver_result['error']}")
                            st.info("💡 Sprawdź czy w Firebase Console → Authentication → Sign-in method → Email/Password jest włączone.")
                        else:
                            st.success(f'{t("verify_email", L)} ({wynik["email"]})')
                        # Do NOT auto-login — require email verification first
                        # Regenerate CAPTCHA
                        q, a = _generate_captcha()
                        st.session_state._captcha_q, st.session_state._captcha_a = q, a
    return False

# =============================================================================
# GŁÓWNA APLIKACJA
# =============================================================================
def main():
    st.set_page_config(page_title="Portfel inwestycyjny", page_icon="📊",
                       layout="wide", initial_sidebar_state="collapsed")

    # --- Autentykacja ---
    if not ekran_autentykacji():
        return

    # --- Firebase ---
    db = inicjalizuj_firebase()
    uid = st.session_state.uid

    # --- Inicjalizacja domyślnych ustawień ---
    if "motyw_ciemny" not in st.session_state: st.session_state.motyw_ciemny = True
    if "paleta" not in st.session_state: st.session_state.paleta = "Oceanic"
    if "aktywny_portfel" not in st.session_state: st.session_state.aktywny_portfel = None
    if "lang" not in st.session_state: st.session_state.lang = "pl"
    L = st.session_state.lang

    # =========================================================================
    # APPLY THEME
    # =========================================================================
    zastosuj_motyw(st.session_state.motyw_ciemny, st.session_state.paleta)
    paleta = PALETY_KOLOROW[st.session_state.paleta]

    # =========================================================================
    # PORTFOLIO LOADING
    # =========================================================================
    portfele = pobierz_portfele(db, uid)
    if not portfele:
        default_name = "My Portfolio" if L == "en" else "Mój Portfel"
        stworz_portfel(db, uid, default_name)
        portfele = pobierz_portfele(db, uid)

    nazwy = [p["nazwa"] for p in portfele]
    ids = [p["id"] for p in portfele]
    if st.session_state.aktywny_portfel not in ids:
        st.session_state.aktywny_portfel = ids[0] if ids else None

    # =========================================================================
    # TOP NAVBAR
    # =========================================================================
    nav_c1, nav_c2, nav_c3, nav_c4 = st.columns([4, 1, 2, 2])

    with nav_c1:
        logo_html = ""
        if os.path.exists(LOGO_PATH):
            with open(LOGO_PATH, "rb") as img_f:
                logo_b64 = base64.b64encode(img_f.read()).decode()
            logo_html = f'<img src="data:image/jpeg;base64,{logo_b64}" width="32" style="border-radius:8px;vertical-align:middle;margin-right:10px;">'
        st.markdown(f'{logo_html}<span class="app-title" style="font-size:1.3rem;">Portfel Inwestycyjny</span>',
                    unsafe_allow_html=True)

    with nav_c2:
        lang_opts = {"🇵🇱": "pl", "🇬🇧": "en"}
        lang_labels = list(lang_opts.keys())
        cur_li = list(lang_opts.values()).index(L) if L in lang_opts.values() else 0
        sel_lang = st.selectbox("lang", lang_labels, index=cur_li, key="lang_nav", label_visibility="collapsed")
        new_lang = lang_opts[sel_lang]
        if new_lang != st.session_state.lang:
            st.session_state.lang = new_lang
            st.rerun()
        L = st.session_state.lang

    with nav_c3:
        wybrany_idx = ids.index(st.session_state.aktywny_portfel) if st.session_state.aktywny_portfel in ids else 0
        wybrany = st.selectbox(t("active_portfolio", L), nazwy, index=wybrany_idx, key="portfel_nav", label_visibility="collapsed")
        st.session_state.aktywny_portfel = ids[nazwy.index(wybrany)]

    with nav_c4:
        uc1, uc2 = st.columns([3, 1])
        with uc1:
            st.markdown(f'<span style="font-size:0.8rem;opacity:0.7;">👤 {st.session_state.email}</span>', unsafe_allow_html=True)
        with uc2:
            if st.button("🚪", key="btn_logout_nav", help=t("logout", L)):
                lang_backup = st.session_state.get("lang", "pl")
                for key in list(st.session_state.keys()): del st.session_state[key]
                st.session_state.lang = lang_backup
                st.rerun()

    # =========================================================================
    # ACTION TABS — Transactions / OCR / Settings
    # =========================================================================
    tab_tx, tab_imp, tab_div, tab_cal, tab_corr, tab_ind, tab_cfg = st.tabs([
        t("nav_transactions", L), t("nav_import", L), t("nav_dividends", L),
        t("nav_calendar", L), t("nav_correlation", L), t("tab_indicators", L), t("nav_settings", L)
    ])

    with tab_tx:
        buy_label = t("buy", L)
        sell_label = t("sell", L)

        opcje_tickerow = [t("type_manually", L)] + list(TICKER_DATABASE.keys())
        wybrany_ticker = st.selectbox(
            t("ticker_search", L), opcje_tickerow, index=0,
            key="ticker_search", help=t("ticker_search_help", L)
        )
        ticker_z_bazy = TICKER_DATABASE.get(wybrany_ticker, "") if wybrany_ticker != t("type_manually", L) else ""

        with st.form("form_tx", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            with fc1:
                ticker_in = st.text_input(t("ticker", L), value=ticker_z_bazy, placeholder="e.g. AAPL, CDR.WA")
                typ = st.radio(t("type", L), [buy_label, sell_label], horizontal=True)
                ilosc = st.number_input(t("quantity", L), min_value=0.0001, value=1.0, step=0.1, format="%.4f")
            with fc2:
                cena = st.number_input(t("purchase_price", L), min_value=0.01, value=100.0, step=0.01, format="%.2f")
                data_tx = st.date_input(t("date", L), value=date.today())
                notatka = st.text_input(t("note_label", L), placeholder=t("note_placeholder", L), key="tx_note")
            dodaj = st.form_submit_button(t("add_btn", L), use_container_width=True)

            if dodaj and st.session_state.aktywny_portfel:
                tk = waliduj_ticker(ticker_in)
                il, cn = waliduj_liczbe(ilosc), waliduj_liczbe(cena)
                if not tk: st.error(t("invalid_ticker", L))
                elif il <= 0: st.error(t("quantity_gt0", L))
                elif cn <= 0: st.error(t("price_gt0", L))
                else:
                    typ_db = "Kupno" if typ == buy_label else "Sprzedaż"
                    if typ_db == "Sprzedaż":
                        trans_list = pobierz_transakcje(db, uid, st.session_state.aktywny_portfel)
                        posiadane = sum(float(tx["ilosc"]) if tx["typ"]=="Kupno" else -float(tx["ilosc"])
                                        for tx in trans_list if tx["ticker"] == tk)
                        if il > posiadane:
                            st.error(f"{t('only_have', L)} {posiadane:.4f} {tk}"); st.stop()
                    tx_data = {"ticker": tk, "ilosc": il, "cena_zakupu": cn, "data": str(data_tx), "typ": typ_db}
                    if notatka.strip():
                        tx_data["notatka"] = notatka.strip()
                    dodaj_transakcje(db, uid, st.session_state.aktywny_portfel, tx_data)
                    st.success(f"✅ {typ}: {il}× {tk} @ ${cn:.2f}")
                    st.rerun()

        # --- Transaction list ---
        st.markdown(t("transactions", L))
        if st.session_state.aktywny_portfel:
            transakcje_lista = pobierz_transakcje(db, uid, st.session_state.aktywny_portfel)
            if transakcje_lista:
                for tx in transakcje_lista:
                    emoji = "🟢" if tx["typ"] == "Kupno" else "🔴"
                    typ_display = t("buy", L) if tx["typ"] == "Kupno" else t("sell", L)
                    tc1, tc2, tc3 = st.columns([4, 0.5, 0.5])
                    with tc1: st.caption(f"{emoji} {typ_display}: {tx['ilosc']}× {tx['ticker']} @ ${float(tx['cena_zakupu']):.2f}")
                    with tc2:
                        note_text = tx.get('notatka', '')
                        if note_text:
                            st.markdown(f'<span title="{note_text}" style="cursor:help;font-size:16px">💡</span>', unsafe_allow_html=True)
                    with tc3:
                        if st.button("🗑️", key=f"del_{tx['id']}"):
                            usun_transakcje(db, uid, st.session_state.aktywny_portfel, tx["id"])
                            st.rerun()
            else:
                st.info(t("no_transactions", L))

    with tab_imp:
        imp_ocr, imp_csv = st.tabs(["📸 OCR", "📄 CSV"])
        with imp_ocr:
            ocr_tab1, ocr_tab2 = st.tabs([t("ocr_upload_label", L), t("ocr_camera_label", L)])
        with ocr_tab1:
            uploaded_file = st.file_uploader(
                t("ocr_upload_label", L), type=["jpg", "jpeg", "png", "webp"],
                key="ocr_upload", label_visibility="collapsed"
            )
        with ocr_tab2:
            camera_file = st.camera_input(t("ocr_camera_label", L), key="ocr_camera", label_visibility="collapsed")

        active_image = uploaded_file or camera_file
        if active_image:
            st.image(active_image, width=200, caption="📷")
            if st.button(t("ocr_analyze_btn", L), key="btn_ocr_analyze", use_container_width=True):
                with st.spinner(t("ocr_analyzing", L)):
                    try:
                        img_bytes = active_image.getvalue()
                        mime = active_image.type if hasattr(active_image, 'type') else "image/jpeg"
                        results = extract_transactions_from_image(img_bytes, mime)
                        st.session_state["_ocr_results"] = results
                    except Exception as e:
                        st.error(f'{t("ocr_error", L)}: {str(e)[:200]}')
                        st.session_state["_ocr_results"] = []

        if st.session_state.get("_ocr_results"):
            ocr_results = st.session_state["_ocr_results"]
            st.markdown(f'<div class="ocr-result-header">{t("ocr_found_n", L).format(len(ocr_results))}</div>', unsafe_allow_html=True)
            st.caption(t("ocr_edit_hint", L))
            ocr_buy = t("buy", L)
            ocr_sell = t("sell", L)
            df_ocr = pd.DataFrame({
                t("ocr_select_col", L): [True] * len(ocr_results),
                t("ocr_ticker_col", L): [r["ticker"] for r in ocr_results],
                t("ocr_qty_col", L): [r["ilosc"] for r in ocr_results],
                t("ocr_price_col", L): [r["cena_zakupu"] for r in ocr_results],
                t("ocr_date_col", L): [r["data"] for r in ocr_results],
                t("ocr_type_col", L): [ocr_buy if r["typ"] == "Kupno" else ocr_sell for r in ocr_results],
            })
            edited_df = st.data_editor(
                df_ocr, use_container_width=True, hide_index=True,
                num_rows="dynamic", key="ocr_editor",
                column_config={
                    t("ocr_select_col", L): st.column_config.CheckboxColumn(default=True),
                    t("ocr_type_col", L): st.column_config.SelectboxColumn(options=[ocr_buy, ocr_sell]),
                }
            )
            col_imp, col_can = st.columns(2)
            with col_imp:
                if st.button(t("ocr_import_btn", L), key="btn_ocr_import", use_container_width=True):
                    if st.session_state.aktywny_portfel and edited_df is not None:
                        selected = edited_df[edited_df[t("ocr_select_col", L)] == True]
                        imported = 0
                        for _, row in selected.iterrows():
                            try:
                                tk = str(row[t("ocr_ticker_col", L)]).strip().upper()
                                il = float(row[t("ocr_qty_col", L)])
                                cn = float(row[t("ocr_price_col", L)])
                                dt = str(row[t("ocr_date_col", L)]).strip()
                                typ_val = str(row[t("ocr_type_col", L)])
                                typ_db = "Kupno" if typ_val == ocr_buy else "Sprzedaż"
                                if tk and il > 0 and cn > 0:
                                    dodaj_transakcje(db, uid, st.session_state.aktywny_portfel,
                                        {"ticker": tk, "ilosc": il, "cena_zakupu": cn, "data": dt, "typ": typ_db})
                                    imported += 1
                            except (ValueError, TypeError):
                                continue
                        if imported > 0:
                            st.success(t("ocr_success", L).format(imported))
                            st.session_state["_ocr_results"] = []
                            st.rerun()
            with col_can:
                if st.button(t("ocr_cancel_btn", L), key="btn_ocr_cancel", use_container_width=True):
                    st.session_state["_ocr_results"] = []
                    st.rerun()

        with imp_csv:
            broker = st.selectbox(t("csv_broker", L), ["XTB", "eToro", "Interactive Brokers", t("csv_generic", L)], key="csv_broker_sel")
            csv_file = st.file_uploader(t("csv_upload", L), type=["csv"], key="csv_upload")

            if csv_file:
                try:
                    raw_df = pd.read_csv(csv_file)
                    st.caption(t("csv_preview", L))
                    st.dataframe(raw_df.head(10), use_container_width=True, hide_index=True)

                    # Column mapping presets
                    COL_MAPS = {
                        "XTB": {"Symbol": "ticker", "Type": "typ", "Volume": "ilosc", "Open Price": "cena_zakupu", "Open Time": "data"},
                        "eToro": {"Instrument": "ticker", "Type": "typ", "Units": "ilosc", "Open Rate": "cena_zakupu", "Open Date": "data"},
                        "Interactive Brokers": {"Symbol": "ticker", "Buy/Sell": "typ", "Quantity": "ilosc", "Price": "cena_zakupu", "Date/Time": "data"},
                    }
                    col_map = COL_MAPS.get(broker, {})

                    # Auto-detect columns if generic
                    if not col_map:
                        for c in raw_df.columns:
                            cl = c.lower()
                            if any(k in cl for k in ["ticker", "symbol", "instrument"]): col_map[c] = "ticker"
                            elif any(k in cl for k in ["type", "typ", "buy", "side"]): col_map[c] = "typ"
                            elif any(k in cl for k in ["quantity", "volume", "qty", "units", "ilosc"]): col_map[c] = "ilosc"
                            elif any(k in cl for k in ["price", "cena", "rate", "cost"]): col_map[c] = "cena_zakupu"
                            elif any(k in cl for k in ["date", "time", "data"]): col_map[c] = "data"

                    if st.button(t("csv_import_btn", L), use_container_width=True, key="btn_csv_import"):
                        if st.session_state.aktywny_portfel and col_map:
                            imported = 0
                            for _, row in raw_df.iterrows():
                                try:
                                    tk_col = next((k for k, v in col_map.items() if v == "ticker"), None)
                                    il_col = next((k for k, v in col_map.items() if v == "ilosc"), None)
                                    cn_col = next((k for k, v in col_map.items() if v == "cena_zakupu"), None)
                                    dt_col = next((k for k, v in col_map.items() if v == "data"), None)
                                    tp_col = next((k for k, v in col_map.items() if v == "typ"), None)

                                    if not all([tk_col, il_col, cn_col]):
                                        continue

                                    tk = str(row[tk_col]).strip().upper()
                                    il = abs(float(row[il_col]))
                                    cn = abs(float(row[cn_col]))
                                    dt = str(row[dt_col])[:10] if dt_col else str(date.today())
                                    raw_typ = str(row[tp_col]).lower() if tp_col else "buy"
                                    typ_db = "Sprzedaż" if any(s in raw_typ for s in ["sell", "sprze", "short"]) else "Kupno"

                                    if tk and il > 0 and cn > 0:
                                        dodaj_transakcje(db, uid, st.session_state.aktywny_portfel,
                                            {"ticker": tk, "ilosc": il, "cena_zakupu": cn, "data": dt, "typ": typ_db})
                                        imported += 1
                                except (ValueError, TypeError, KeyError):
                                    continue
                            if imported > 0:
                                st.success(t("csv_success", L).format(imported))
                                st.rerun()
                            else:
                                st.error(t("csv_error", L))
                except Exception as e:
                    st.error(f"{t('csv_error', L)}: {e}")

    # ===================== TAB: DIVIDENDS =====================
    with tab_div:
        if st.session_state.aktywny_portfel:
            tx_list = pobierz_transakcje(db, uid, st.session_state.aktywny_portfel)
            tickers_in = list(set(tx["ticker"] for tx in tx_list)) if tx_list else []
            if tickers_in:
                div_data = []
                for tk in tickers_in:
                    d = pobierz_dywidendy(tk)
                    qty = sum(float(tx["ilosc"]) if tx["typ"]=="Kupno" else -float(tx["ilosc"])
                              for tx in tx_list if tx["ticker"] == tk)
                    annual = qty * d["yield"] * 100 if d["yield"] else 0
                    div_data.append({
                        t("div_ticker", L): tk,
                        t("div_yield", L): f"{d['yield']*100:.2f}%" if d["yield"] else "—",
                        t("div_last", L): d["last"],
                        t("div_annual", L): f"${annual:.2f}" if annual > 0 else "—",
                    })
                st.dataframe(pd.DataFrame(div_data), use_container_width=True, hide_index=True)
            else:
                st.info(t("div_no_data", L))
        else:
            st.info(t("div_no_data", L))

    # ===================== TAB: CALENDAR =====================
    with tab_cal:
        cal_search = st.text_input("🔍", placeholder="AAPL, MSFT, CDR.WA...", key="cal_search", label_visibility="collapsed")

        cal_tickers = []
        if st.session_state.aktywny_portfel:
            tx_list = pobierz_transakcje(db, uid, st.session_state.aktywny_portfel)
            cal_tickers = list(set(tx["ticker"] for tx in tx_list)) if tx_list else []

        if cal_search.strip():
            extra = [s.strip().upper() for s in cal_search.split(",") if s.strip()]
            cal_tickers = list(set(cal_tickers + extra))

        if cal_tickers:
            with st.spinner("⏳"):
                for tk in cal_tickers:
                    try:
                        ticker_obj = yf.Ticker(tk)
                        info = ticker_obj.info or {}
                        name = info.get("shortName") or info.get("longName") or tk
                        sector = info.get("sector", "—")
                        mkt_cap = info.get("marketCap")
                        mkt_str = f"${mkt_cap/1e9:.1f}B" if mkt_cap and mkt_cap > 1e9 else (f"${mkt_cap/1e6:.0f}M" if mkt_cap else "—")
                        cur_price = info.get("currentPrice") or info.get("regularMarketPrice")
                        price_str = f"${cur_price:,.2f}" if cur_price else "—"

                        # Company header card
                        st.markdown(
                            f'<div style="padding:10px 14px;margin:8px 0 4px 0;border-radius:10px;'
                            f'background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.2);">'
                            f'<span style="font-size:16px;font-weight:700">{tk}</span> '
                            f'<span style="color:#888;font-size:14px">— {name}</span><br>'
                            f'<span style="color:#aaa;font-size:12px">🏢 {sector} · 💰 {mkt_str} · 📈 {price_str}</span></div>',
                            unsafe_allow_html=True
                        )

                        events_found = False

                        # 1. Earnings dates from .info
                        earnings_dates_raw = info.get("earningsTimestamp") or info.get("earningsTimestampStart")
                        if earnings_dates_raw:
                            from datetime import timezone
                            e_date = datetime.fromtimestamp(earnings_dates_raw, tz=timezone.utc).strftime("%Y-%m-%d")
                            st.markdown(
                                f'<div style="padding:6px 12px;margin:2px 0 2px 16px;border-left:3px solid #10b981;'
                                f'font-size:13px">📊 <b>Earnings</b> · 📅 {e_date}</div>',
                                unsafe_allow_html=True)
                            events_found = True

                        # 2. Ex-dividend date from .info
                        ex_div = info.get("exDividendDate")
                        if ex_div:
                            from datetime import timezone
                            ex_date = datetime.fromtimestamp(ex_div, tz=timezone.utc).strftime("%Y-%m-%d") if isinstance(ex_div, (int, float)) else str(ex_div)[:10]
                            div_rate = info.get("dividendRate")
                            div_yield = info.get("dividendYield")
                            desc = f"${div_rate:.2f}/yr" if div_rate else ""
                            if div_yield:
                                desc += f" ({div_yield*100:.2f}%)"
                            st.markdown(
                                f'<div style="padding:6px 12px;margin:2px 0 2px 16px;border-left:3px solid #f59e0b;'
                                f'font-size:13px">💰 <b>Ex-Dividend</b> · 📅 {ex_date}'
                                f'{" · " + desc if desc else ""}</div>',
                                unsafe_allow_html=True)
                            events_found = True

                        # 3. Earnings history from .earnings_dates
                        try:
                            ed = ticker_obj.earnings_dates
                            if ed is not None and not ed.empty:
                                upcoming = ed[ed.index >= pd.Timestamp.now(tz="UTC")]
                                show_ed = upcoming.head(3) if not upcoming.empty else ed.head(3)
                                for idx, row in show_ed.iterrows():
                                    d = idx.strftime("%Y-%m-%d")
                                    eps_est = row.get("EPS Estimate", None)
                                    eps_act = row.get("Reported EPS", None)
                                    desc_parts = []
                                    if pd.notna(eps_est): desc_parts.append(f"Est: ${eps_est:.2f}")
                                    if pd.notna(eps_act): desc_parts.append(f"Act: ${eps_act:.2f}")
                                    desc = " · ".join(desc_parts)
                                    label = "📊 Earnings" if pd.isna(eps_act) else "📋 Earnings (reported)"
                                    st.markdown(
                                        f'<div style="padding:6px 12px;margin:2px 0 2px 16px;border-left:3px solid #8b5cf6;'
                                        f'font-size:13px">{label} · 📅 {d}'
                                        f'{" · " + desc if desc else ""}</div>',
                                        unsafe_allow_html=True)
                                    events_found = True
                        except Exception:
                            pass

                        if not events_found:
                            st.caption(f"  ⚠️ {t('cal_no_events', L)}")

                    except Exception:
                        st.caption(f"⚠️ {tk}: {t('cal_no_events', L)}")
        else:
            st.info(t("cal_no_events", L))

    # ===================== TAB: CORRELATION =====================
    with tab_corr:
        if st.session_state.aktywny_portfel:
            tx_list = pobierz_transakcje(db, uid, st.session_state.aktywny_portfel)
            tickers_in = list(set(tx["ticker"] for tx in tx_list)) if tx_list else []
            all_options = tickers_in + ["^GSPC", "WIG20.WA", "BTC-USD", "ETH-USD"]
            selected = st.multiselect(t("corr_select", L), all_options, default=tickers_in[:4], key="corr_assets")
            corr_days = st.slider(t("corr_period", L), 30, 365, 90, key="corr_days")

            if len(selected) >= 2:
                with st.spinner("..."):
                    corr_matrix = pobierz_korelacje(tuple(selected), corr_days)
                if not corr_matrix.empty:
                    fig_corr = px.imshow(
                        corr_matrix, text_auto=".2f", color_continuous_scale="RdBu_r",
                        zmin=-1, zmax=1, aspect="auto",
                        title=t("corr_heatmap", L)
                    )
                    fig_corr.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter"), height=400,
                        margin=dict(t=40, b=20, l=20, r=20),
                        transition=dict(duration=500, easing="cubic-in-out"),
                    )
                    st.plotly_chart(fig_corr, use_container_width=True, config=CHART_CONFIG)

                    # Price chart comparison
                    st.markdown(f"**{t('corr_chart', L)}**")
                    end_dt = datetime.now()
                    start_dt = end_dt - timedelta(days=corr_days)
                    price_data = yf.download(selected, start=start_dt, end=end_dt, progress=False)["Close"]
                    if not price_data.empty:
                        normalized = (price_data / price_data.iloc[0]) * 100
                        fig_price = px.line(normalized, title=None)
                        fig_price.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(family="Inter"), height=350,
                            margin=dict(t=10, b=30, l=40, r=20),
                            yaxis_title="%", xaxis_title="",
                            legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
                            hovermode="x unified",
                            transition=dict(duration=500, easing="cubic-in-out"),
                        )
                        st.plotly_chart(fig_price, use_container_width=True, config=CHART_CONFIG)
            else:
                st.info(t("corr_no_data", L))
        else:
            st.info(t("corr_no_data", L))

    # ===================== TAB: INDICATORS =====================
    with tab_ind:
        # --- Compact CSS for TradingView-style toolbar ---
        st.markdown("""
        <style>
        /* Compact portfolio chips */
        div[data-testid="stHorizontalBlock"]:has(button[kind="secondary"]) .stButton > button,
        div.tv-chips .stButton > button,
        div.tv-intervals .stButton > button {
            padding: 2px 10px !important;
            font-size: 12px !important;
            min-height: 28px !important;
            height: 28px !important;
            line-height: 1 !important;
            border-radius: 4px !important;
        }
        div.tv-chips .stButton > button[kind="primary"],
        div.tv-intervals .stButton > button[kind="primary"] {
            padding: 2px 10px !important;
            font-size: 12px !important;
            min-height: 28px !important;
            height: 28px !important;
        }
        div.tv-chips, div.tv-intervals {
            margin-bottom: -10px !important;
        }
        div.tv-chips [data-testid="stHorizontalBlock"],
        div.tv-intervals [data-testid="stHorizontalBlock"] {
            gap: 0.3rem !important;
        }
        div.tv-intervals .stSelectbox > div > div {
            min-height: 28px !important;
            font-size: 12px !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # --- Unified Ticker Search (TradingView-style) ---
        portfolio_tickers = []
        if st.session_state.aktywny_portfel:
            tx_l = pobierz_transakcje(db, uid, st.session_state.aktywny_portfel)
            portfolio_tickers = sorted(set(tx["ticker"] for tx in tx_l)) if tx_l else []

        # Quick-access chips for portfolio tickers (compact)
        if portfolio_tickers:
            with st.container():
                st.markdown('<div class="tv-chips">', unsafe_allow_html=True)
                chip_cols = st.columns(min(len(portfolio_tickers), 10) + 1)
                for i, tk in enumerate(portfolio_tickers[:10]):
                    with chip_cols[i]:
                        if st.button(tk, key=f"ind_chip_{tk}", use_container_width=True,
                                     type="primary" if st.session_state.get("ind_search", "") == tk else "secondary"):
                            st.session_state.ind_search = tk
                            st.rerun()
                with chip_cols[-1]:
                    st.markdown("<small style='color:#787B86'>portfel</small>", unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

        # Single search input
        search_val = st.text_input("Search ticker", key="ind_search",
                                    placeholder="AAPL, MSTR, BTC-USD, ETH, SOL...",
                                    label_visibility="collapsed")
        ind_ticker = search_val.strip().upper() if search_val.strip() else (portfolio_tickers[0] if portfolio_tickers else "AAPL")
        # Show source badge
        source_label = "BloFin (real-time)" if is_crypto(ind_ticker) else "yfinance"
        st.caption(f"**{ind_ticker}** — {source_label}")

        # ======= CANDLE INTERVAL SELECTOR (TradingView-style) =======
        # Each entry: (yf_interval, yf_period_or_days, resample_rule_or_None)
        CANDLE_INTERVALS = {
            "15m":  ("15m",  60,   None),
            "30m":  ("30m",  60,   None),
            "1h":   ("1h",   730,  None),
            "2h":   ("1h",   730,  "2h"),
            "4h":   ("1h",   730,  "4h"),
            "12h":  ("1h",   730,  "12h"),
            "1D":   ("1d",   3650, None),
            "3D":   ("1d",   3650, "3D"),
            "5D":   ("1d",   3650, "5D"),
            "1W":   ("1wk",  3650, None),
            "1M":   ("1mo",  7300, None),
        }

        # Default view ranges (approx candles to show initially per interval)
        DEFAULT_VIEW_DAYS = {
            "15m": 3, "30m": 5, "1h": 14, "2h": 21, "4h": 30,
            "12h": 60, "1D": 90, "3D": 180, "5D": 365, "1W": 730, "1M": 1825,
        }

        # --- Favorites (pinned intervals, max 5) — persist to Firestore ---
        if "ind_fav_intervals" not in st.session_state or "ind_interval" not in st.session_state:
            # Load saved settings from Firestore
            try:
                settings_ref = db.collection("users").document(uid).collection("settings").document("indicators")
                saved = settings_ref.get()
                if saved.exists:
                    d = saved.to_dict()
                    if "ind_fav_intervals" not in st.session_state:
                        st.session_state.ind_fav_intervals = d.get("fav_intervals", ["1h", "4h", "1D", "1W", "1M"])
                    if "ind_interval" not in st.session_state:
                        st.session_state.ind_interval = d.get("interval", "1D")
                else:
                    if "ind_fav_intervals" not in st.session_state:
                        st.session_state.ind_fav_intervals = ["1h", "4h", "1D", "1W", "1M"]
                    if "ind_interval" not in st.session_state:
                        st.session_state.ind_interval = "1D"
            except Exception:
                if "ind_fav_intervals" not in st.session_state:
                    st.session_state.ind_fav_intervals = ["1h", "4h", "1D", "1W", "1M"]
                if "ind_interval" not in st.session_state:
                    st.session_state.ind_interval = "1D"
        # Guard against stale session
        if st.session_state.ind_interval not in CANDLE_INTERVALS:
            st.session_state.ind_interval = "1D"

        # --- Toolbar row: pinned favorites + dropdown for the rest ---
        fav_list = st.session_state.ind_fav_intervals
        other_intervals = [k for k in CANDLE_INTERVALS if k not in fav_list]

        st.markdown('<div class="tv-intervals">', unsafe_allow_html=True)
        toolbar_cols = st.columns(len(fav_list) + 1)
        for i, label in enumerate(fav_list):
            with toolbar_cols[i]:
                is_active = st.session_state.ind_interval == label
                if st.button(label, key=f"ind_iv_{label}", use_container_width=True,
                             type="primary" if is_active else "secondary"):
                    st.session_state.ind_interval = label
                    # Persist to Firestore
                    try:
                        db.collection("users").document(uid).collection("settings").document("indicators").set(
                            {"interval": label, "fav_intervals": st.session_state.ind_fav_intervals}, merge=True)
                    except Exception:
                        pass
                    st.rerun()
        # "More" dropdown for non-pinned intervals
        with toolbar_cols[-1]:
            more_choice = st.selectbox(
                "more", options=["..."] + other_intervals,
                index=0, key="ind_more_iv", label_visibility="collapsed",
            )
            if more_choice != "..." and more_choice != st.session_state.ind_interval:
                st.session_state.ind_interval = more_choice
                try:
                    db.collection("users").document(uid).collection("settings").document("indicators").set(
                        {"interval": more_choice, "fav_intervals": st.session_state.ind_fav_intervals}, merge=True)
                except Exception:
                    pass
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # --- Pin/Unpin management (expander) ---
        with st.expander(t("ind_fav_label", L), expanded=False):
            st.caption(t("ind_fav_caption", L))
            new_favs = []
            cols_fav = st.columns(len(CANDLE_INTERVALS))
            for idx, iv_name in enumerate(CANDLE_INTERVALS.keys()):
                with cols_fav[idx]:
                    checked = st.checkbox(iv_name, value=iv_name in fav_list, key=f"fav_cb_{iv_name}")
                    if checked:
                        new_favs.append(iv_name)
            if new_favs != fav_list:
                if len(new_favs) <= 5:
                    st.session_state.ind_fav_intervals = new_favs
                    # Persist to Firestore
                    try:
                        db.collection("users").document(uid).collection("settings").document("indicators").set(
                            {"fav_intervals": new_favs, "interval": st.session_state.ind_interval}, merge=True)
                    except Exception:
                        pass
                    st.rerun()
                else:
                    st.warning("Max 5!")

        current_iv = st.session_state.ind_interval
        yf_interval, max_days, resample_rule = CANDLE_INTERVALS[current_iv]
        view_days = DEFAULT_VIEW_DAYS[current_iv]

        # Indicator selection
        INDICATORS = ["SMA 20", "SMA 50", "SMA 200", "EMA 12", "EMA 26", "Bollinger Bands", "RSI", "MACD", "Volume"]
        selected_ind = st.multiselect(t("ind_select_indicators", L), INDICATORS, default=["SMA 20", "RSI"], key="ind_sel")

        if ind_ticker:
            with st.spinner("⏳"):
                use_blofin = is_crypto(ind_ticker)
                end_dt = date.today()

                if use_blofin:
                    # --- BloFin API for crypto (real-time) ---
                    inst_id = ticker_to_blofin(ind_ticker)
                    bf_bar = BLOFIN_BAR_MAP.get(current_iv, "1D")
                    # Crypto: deeper history (3 months for all intervals)
                    CRYPTO_VIEW_DAYS = {
                        "15m": 90, "30m": 90, "1h": 90, "2h": 90, "4h": 90,
                        "12h": 180, "1D": 365, "3D": 365, "5D": 365, "1W": 730, "1M": 1825,
                    }
                    view_days = CRYPTO_VIEW_DAYS.get(current_iv, view_days)
                    candle_est = {"15m": 96, "30m": 48, "1h": 24, "2h": 12, "4h": 6,
                                  "12h": 2, "1D": 1, "3D": 0.33, "5D": 0.2, "1W": 0.14, "1M": 0.033}
                    per_day = candle_est.get(current_iv, 1)
                    limit = max(int(view_days * per_day * 1.3) + 220, 300)  # extra for SMA 200
                    df = fetch_blofin_candles(inst_id, bf_bar, limit)
                    # Resample 5D from 1D if needed
                    if current_iv == "5D" and not df.empty:
                        df = df.resample("5D").agg({
                            "Open": "first", "High": "max", "Low": "min",
                            "Close": "last", "Volume": "sum"}).dropna()
                else:
                    # --- yfinance for stocks ---
                    extra_days = 220 if yf_interval in ("1d", "1wk", "1mo") else 30
                    start_dt = end_dt - timedelta(days=min(view_days + extra_days, max_days))
                    df = yf.download(ind_ticker, start=start_dt, end=end_dt,
                                     interval=yf_interval, progress=False)

                if df.empty or len(df) < 2:
                    st.warning(t("ind_no_data", L))
                else:
                    # Flatten MultiIndex columns if needed
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)

                    # --- Resample if needed (yfinance only: 2h, 4h, 12h, 3D, 5D) ---
                    if resample_rule and not use_blofin:
                        # Map our labels to pandas offset aliases
                        resample_map = {"2h": "2h", "4h": "4h", "12h": "12h", "3D": "3D", "5D": "5D"}
                        rule = resample_map.get(resample_rule, resample_rule)
                        df = df.resample(rule).agg({
                            "Open": "first", "High": "max", "Low": "min",
                            "Close": "last", "Volume": "sum",
                        }).dropna()

                    close = df["Close"].squeeze()
                    high = df["High"].squeeze()
                    low = df["Low"].squeeze()
                    open_price = df["Open"].squeeze()
                    volume = df["Volume"].squeeze()

                    # Calculate indicators
                    calc = {}
                    if "SMA 20" in selected_ind: calc["SMA 20"] = close.rolling(20).mean()
                    if "SMA 50" in selected_ind: calc["SMA 50"] = close.rolling(50).mean()
                    if "SMA 200" in selected_ind: calc["SMA 200"] = close.rolling(200).mean()
                    if "EMA 12" in selected_ind: calc["EMA 12"] = close.ewm(span=12).mean()
                    if "EMA 26" in selected_ind: calc["EMA 26"] = close.ewm(span=26).mean()
                    if "Bollinger Bands" in selected_ind:
                        sma20 = close.rolling(20).mean()
                        std20 = close.rolling(20).std()
                        calc["BB Upper"] = sma20 + 2 * std20
                        calc["BB Lower"] = sma20 - 2 * std20
                        calc["BB Mid"] = sma20
                    rsi_data = None
                    if "RSI" in selected_ind:
                        delta = close.diff()
                        gain = delta.where(delta > 0, 0).rolling(14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                        rs = gain / loss
                        rsi_data = 100 - (100 / (1 + rs))
                    macd_data = None
                    macd_signal = None
                    if "MACD" in selected_ind:
                        ema12 = close.ewm(span=12).mean()
                        ema26 = close.ewm(span=26).mean()
                        macd_data = ema12 - ema26
                        macd_signal = macd_data.ewm(span=9).mean()

                    # Trim to requested timeframe
                    trim_start = pd.Timestamp(end_dt - timedelta(days=view_days))
                    # Handle tz-aware index (yfinance) vs tz-naive (BloFin)
                    if hasattr(close.index, 'tz') and close.index.tz is not None:
                        trim_start = trim_start.tz_localize(close.index.tz)
                    close = close[close.index >= trim_start]
                    high = high[high.index >= trim_start]
                    low = low[low.index >= trim_start]
                    volume = volume[volume.index >= trim_start]
                    open_price = open_price[open_price.index >= trim_start]
                    for k in calc: calc[k] = calc[k][calc[k].index >= trim_start]
                    if rsi_data is not None: rsi_data = rsi_data[rsi_data.index >= trim_start]
                    if macd_data is not None:
                        macd_data = macd_data[macd_data.index >= trim_start]
                        macd_signal = macd_signal[macd_signal.index >= trim_start]

                    # Determine subplot layout
                    n_sub = 1
                    sub_map = {}
                    if "Volume" in selected_ind: n_sub += 1; sub_map["Volume"] = n_sub
                    if "RSI" in selected_ind: n_sub += 1; sub_map["RSI"] = n_sub
                    if "MACD" in selected_ind: n_sub += 1; sub_map["MACD"] = n_sub

                    heights = [0.5] + [0.5 / max(n_sub - 1, 1)] * (n_sub - 1) if n_sub > 1 else [1]
                    from plotly.subplots import make_subplots
                    fig = make_subplots(rows=n_sub, cols=1, shared_xaxes=True,
                                        vertical_spacing=0.03, row_heights=heights)

                    is_dark = st.session_state.motyw_ciemny

                    # --- TradingView color palette ---
                    tv_bg = "#131722" if is_dark else "#FFFFFF"
                    tv_grid = "#363A45" if is_dark else "#E0E3EB"
                    tv_text = "#D1D4DC" if is_dark else "#131722"
                    tv_axis = "#787B86"
                    tv_green = "#26a69a"   # TradingView up candle
                    tv_red = "#ef5350"     # TradingView down candle
                    tv_cross = "#9598A1" if is_dark else "#9598A1"

                    # Candlestick
                    fig.add_trace(go.Candlestick(
                        x=close.index, open=open_price,
                        high=high, low=low, close=close, name=ind_ticker,
                        increasing=dict(line=dict(color=tv_green, width=1), fillcolor=tv_green),
                        decreasing=dict(line=dict(color=tv_red, width=1), fillcolor=tv_red),
                        whiskerwidth=0.5,
                    ), row=1, col=1)

                    # --- Current price line (dashed) with label ---
                    last_price = float(close.iloc[-1])
                    price_color = tv_green if last_price >= float(open_price.iloc[-1]) else tv_red
                    fig.add_hline(
                        y=last_price, line_dash="dash", line_color=price_color, line_width=1,
                        row=1, col=1,
                        annotation_text=f"  {last_price:,.2f}",
                        annotation_position="right",
                        annotation=dict(
                            font=dict(size=11, color="#fff", family="Inter"),
                            bgcolor=price_color, bordercolor=price_color,
                            borderwidth=1, borderpad=3,
                        ),
                    )

                    # Overlay indicators on price chart
                    overlay_colors = {"SMA 20": "#2962FF", "SMA 50": "#FF6D00", "SMA 200": "#E91E63",
                                      "EMA 12": "#7B1FA2", "EMA 26": "#FF6F00"}
                    for ind_name, series in calc.items():
                        if ind_name in overlay_colors:
                            fig.add_trace(go.Scatter(
                                x=series.index, y=series.values, mode="lines",
                                name=ind_name, line=dict(color=overlay_colors[ind_name], width=1.5),
                            ), row=1, col=1)
                    # Bollinger Bands (with fill between upper/lower)
                    if "BB Upper" in calc:
                        fig.add_trace(go.Scatter(
                            x=calc["BB Upper"].index, y=calc["BB Upper"].values, mode="lines",
                            name="BB Upper", line=dict(color="#2962FF", width=1, dash="dot"),
                        ), row=1, col=1)
                        fig.add_trace(go.Scatter(
                            x=calc["BB Lower"].index, y=calc["BB Lower"].values, mode="lines",
                            name="BB Lower", line=dict(color="#2962FF", width=1, dash="dot"),
                            fill="tonexty", fillcolor="rgba(41,98,255,0.06)",
                        ), row=1, col=1)
                        fig.add_trace(go.Scatter(
                            x=calc["BB Mid"].index, y=calc["BB Mid"].values, mode="lines",
                            name="BB Mid", line=dict(color="#2962FF", width=1, dash="dash"),
                        ), row=1, col=1)

                    # Volume subplot
                    if "Volume" in sub_map:
                        colors = [tv_green if c >= o else tv_red
                                  for c, o in zip(close.values, open_price.values)]
                        fig.add_trace(go.Bar(
                            x=volume.index, y=volume.values, name="Volume",
                            marker_color=colors, opacity=0.45,
                            marker_line_width=0,
                        ), row=sub_map["Volume"], col=1)

                    # RSI subplot
                    if "RSI" in sub_map and rsi_data is not None:
                        fig.add_trace(go.Scatter(
                            x=rsi_data.index, y=rsi_data.values, mode="lines",
                            name="RSI", line=dict(color="#7B1FA2", width=1.5),
                        ), row=sub_map["RSI"], col=1)
                        # Overbought / oversold zones
                        fig.add_hrect(y0=70, y1=100, fillcolor="rgba(239,83,80,0.08)",
                                      line_width=0, row=sub_map["RSI"], col=1)
                        fig.add_hrect(y0=0, y1=30, fillcolor="rgba(38,166,154,0.08)",
                                      line_width=0, row=sub_map["RSI"], col=1)
                        fig.add_hline(y=70, line_dash="dash", line_color=tv_red, line_width=0.7,
                                      row=sub_map["RSI"], col=1)
                        fig.add_hline(y=30, line_dash="dash", line_color=tv_green, line_width=0.7,
                                      row=sub_map["RSI"], col=1)
                        fig.add_hline(y=50, line_dash="dot", line_color=tv_axis, line_width=0.5,
                                      row=sub_map["RSI"], col=1)
                        fig.update_yaxes(range=[0, 100], row=sub_map["RSI"], col=1)

                    # MACD subplot
                    if "MACD" in sub_map and macd_data is not None:
                        fig.add_trace(go.Scatter(
                            x=macd_data.index, y=macd_data.values, mode="lines",
                            name="MACD", line=dict(color="#2962FF", width=1.5),
                        ), row=sub_map["MACD"], col=1)
                        fig.add_trace(go.Scatter(
                            x=macd_signal.index, y=macd_signal.values, mode="lines",
                            name="Signal", line=dict(color="#FF6D00", width=1.5),
                        ), row=sub_map["MACD"], col=1)
                        histogram = macd_data - macd_signal
                        hist_colors = ["rgba(38,166,154,0.6)" if v >= 0 else "rgba(239,83,80,0.6)"
                                       for v in histogram.values]
                        fig.add_trace(go.Bar(
                            x=histogram.index, y=histogram.values, name="Histogram",
                            marker_color=hist_colors, marker_line_width=0,
                        ), row=sub_map["MACD"], col=1)
                        fig.add_hline(y=0, line_dash="solid", line_color=tv_grid, line_width=0.5,
                                      row=sub_map["MACD"], col=1)

                    # --- TradingView-style layout ---
                    total_h = 550 + (n_sub - 1) * 200
                    fig.update_layout(
                        height=total_h,
                        paper_bgcolor=tv_bg,
                        plot_bgcolor=tv_bg,
                        font=dict(color=tv_text, family="'Trebuchet MS', Inter, sans-serif", size=12),
                        showlegend=True,
                        legend=dict(
                            orientation="h", yanchor="bottom", y=1.02,
                            xanchor="right", x=1,
                            font=dict(size=10, color=tv_axis),
                            bgcolor="rgba(0,0,0,0)",
                        ),
                        margin=dict(l=0, r=60, t=30, b=20),
                        xaxis_rangeslider_visible=False,
                        hovermode="x unified",
                        hoverlabel=dict(
                            bgcolor=tv_bg, bordercolor=tv_grid,
                            font=dict(color=tv_text, size=12, family="Inter"),
                        ),
                        dragmode="pan",
                    )

                    # --- Ticker watermark ---
                    fig.add_annotation(
                        text=ind_ticker,
                        xref="paper", yref="paper",
                        x=0.5, y=0.5,
                        showarrow=False,
                        font=dict(size=60, color=tv_grid, family="Inter"),
                        opacity=0.15 if is_dark else 0.08,
                    )

                    # --- Style all axes (TradingView) ---
                    for i in range(1, n_sub + 1):
                        fig.update_xaxes(
                            gridcolor=tv_grid, gridwidth=0.5,
                            zeroline=False,
                            showline=True, linecolor=tv_grid, linewidth=0.5,
                            tickfont=dict(color=tv_axis, size=10),
                            spikemode="across", spikesnap="cursor",
                            spikecolor=tv_cross, spikethickness=0.5, spikedash="solid",
                            row=i, col=1,
                            fixedrange=False,
                        )
                        fig.update_yaxes(
                            gridcolor=tv_grid, gridwidth=0.5,
                            zeroline=False,
                            showline=True, linecolor=tv_grid, linewidth=0.5,
                            side="right",
                            tickfont=dict(color=tv_axis, size=10),
                            spikemode="across", spikesnap="cursor",
                            spikecolor=tv_cross, spikethickness=0.5, spikedash="solid",
                            row=i, col=1,
                            fixedrange=False,
                        )

                    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)

    with tab_cfg:
        cfg_c1, cfg_c2 = st.columns(2)
        with cfg_c1:
            # --- Theme ---
            st.session_state.motyw_ciemny = st.toggle(t("dark_mode", L), value=st.session_state.motyw_ciemny)
            st.session_state.paleta = st.selectbox(t("palette", L), list(PALETY_KOLOROW.keys()),
                index=list(PALETY_KOLOROW.keys()).index(st.session_state.paleta))
            kolory_html = " ".join(f'<span style="display:inline-block;width:18px;height:18px;'
                f'border-radius:50%;background:{c};margin:2px;"></span>' for c in PALETY_KOLOROW[st.session_state.paleta])
            st.markdown(kolory_html, unsafe_allow_html=True)

        with cfg_c2:
            # --- Portfolio management ---
            st.markdown(t("portfolios", L))
            col_np1, col_np2 = st.columns([3, 1])
            with col_np1:
                nowa_nazwa = st.text_input(t("new_portfolio", L), placeholder=t("name_placeholder", L), label_visibility="collapsed")
            with col_np2:
                if st.button("➕", key="btn_nowy_portfel"):
                    nazwa_clean = sanitize_input(nowa_nazwa.strip(), 50)
                    if nazwa_clean:
                        wyn = stworz_portfel(db, uid, nazwa_clean)
                        if wyn.get("error"): st.error(wyn["error"])
                        else: st.success(f"✅ '{nazwa_clean}' {t('portfolio_created', L)}"); st.rerun()

            if len(portfele) > 1:
                if st.button(t("delete_portfolio", L), key="btn_usun_portfel"):
                    usun_portfel(db, uid, st.session_state.aktywny_portfel)
                    st.session_state.aktywny_portfel = None
                    st.rerun()

            buy_label = t("buy", L)
            sell_label = t("sell", L)
    # =========================================================================
    # DASHBOARD
    # =========================================================================
    st.markdown(f'<p class="app-subtitle">{t("app_subtitle", L)}</p>', unsafe_allow_html=True)


    if not st.session_state.aktywny_portfel:
        st.warning(t("create_portfolio", L)); return

    transakcje = pobierz_transakcje(db, uid, st.session_state.aktywny_portfel)
    if not transakcje:
        st.markdown(t("welcome", L))
        return

    with st.spinner(t("fetching_data", L)):
        portfel_df = oblicz_portfel(transakcje)

    if portfel_df.empty:
        st.warning(t("no_positions", L)); return

    # --- METRIC CARDS (4 karty) ---
    lw = portfel_df["Wartość ($)"].sum()
    lk = (portfel_df["Śr. Cena Zakupu ($)"] * portfel_df["Ilość"]).sum()
    lz = lw - lk
    lr = ((lw - lk) / lk * 100) if lk > 0 else 0
    kz = "delta-positive" if lz >= 0 else "delta-negative"
    zn = "+" if lz >= 0 else ""

    dzienny_pl = sum(portfel_df["Wartość ($)"] * portfel_df["Zmienność (%)"] / 100)
    dzienny_pct = (dzienny_pl / lw * 100) if lw > 0 else 0
    dz_kz = "delta-positive" if dzienny_pl >= 0 else "delta-negative"
    dz_zn = "+" if dzienny_pl >= 0 else ""

    najgorszy = portfel_df.loc[portfel_df["ROI (%)"].idxmin()]
    najlepszy = portfel_df.loc[portfel_df["ROI (%)"].idxmax()]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="label">{t("portfolio_value", L)}</div>'
            f'<div class="value">${lw:,.2f}</div>'
            f'<div class="sub" style="color:{paleta[2]}">{t("invested", L)}: ${lk:,.2f}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="label">{t("profit_loss", L)}</div>'
            f'<div class="value {kz}">{zn}${abs(lz):,.2f}</div>'
            f'<div class="sub {kz}">{zn}{lr:.2f}%</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="label">{t("today_change", L)}</div>'
            f'<div class="value {dz_kz}">{dz_zn}${abs(dzienny_pl):,.2f}</div>'
            f'<div class="sub {dz_kz}">{dz_zn}{dzienny_pct:.2f}%</div></div>', unsafe_allow_html=True)
    with c4:
        ng_roi = najgorszy["ROI (%)"]
        ng_kz = "delta-negative" if ng_roi < 0 else "delta-positive"
        label4 = t("biggest_loss", L) if ng_roi < 0 else t("best_position", L)
        st.markdown(f'<div class="metric-card"><div class="label">{label4}</div>'
            f'<div class="value {ng_kz}">{najgorszy["Ticker"] if ng_roi < 0 else najlepszy["Ticker"]}</div>'
            f'<div class="{"loss-badge" if ng_roi < 0 else "sub delta-positive"}">{"" if ng_roi < 0 else "+"}{(ng_roi if ng_roi < 0 else najlepszy["ROI (%)"]):+.2f}%</div></div>', unsafe_allow_html=True)

    # --- Sector Allocation (compact) ---
    sektory = {}
    for _, row in portfel_df.iterrows():
        sektor = pobierz_sektor(row["Ticker"])
        sektor = sektor if sektor != "Unknown" else t("sector_unknown", L)
        sektory[sektor] = sektory.get(sektor, 0) + row["Wartość ($)"]
    if sektory:
        pie_c1, pie_c2 = st.columns([1, 3])
        with pie_c1:
            fig_pie = px.pie(
                names=list(sektory.keys()), values=list(sektory.values()),
                hole=0.55, color_discrete_sequence=paleta,
            )
            fig_pie.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=5, b=5, l=5, r=5),
                height=160, showlegend=False,
                font=dict(size=10, family="Inter"),
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent")
            st.plotly_chart(fig_pie, use_container_width=True, config=CHART_CONFIG)
        with pie_c2:
            st.caption(t("sector_title", L))
            for s, v in sorted(sektory.items(), key=lambda x: -x[1]):
                pct = v / sum(sektory.values()) * 100
                st.markdown(f"<small>**{s}** — ${v:,.0f} ({pct:.1f}%)</small>", unsafe_allow_html=True)

    # =========================================================================
    # CHART TABS — ARCHITECT + CHART MASTER
    # =========================================================================
    is_dark = st.session_state.motyw_ciemny
    font_col = "#FAFAFA" if is_dark else "#1A1A2E"
    grid_col = "rgba(255,215,0,0.05)" if is_dark else "rgba(0,0,0,0.05)"
    chart_line_color = "#FFD700"  # Gold — main chart color
    layout_base = dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=font_col, family="Inter"),
        margin=dict(t=20, b=40, l=50, r=30), height=600,
        hovermode="x unified",
        transition=dict(duration=500, easing="cubic-in-out"),
    )

    # --- Pobierz dane dla wykresów z cache ---
    with st.spinner(t("generating_history", L)):
        roi_df = oblicz_roi_portfela(transakcje)
        hist_df = oblicz_historie_portfela(transakcje)

    # Przygotuj serie do wykresów
    wartosci_serie = None
    kapital_serie = None
    stats = None

    if not roi_df.empty and len(roi_df) > 1:
        wartosci_serie = pd.Series(roi_df["Wartość ($)"].values, index=pd.to_datetime(roi_df["Data"]))
        kapital_serie = pd.Series(roi_df["Kapitał ($)"].values, index=pd.to_datetime(roi_df["Data"]))
        stats = oblicz_statystyki(wartosci_serie, kapital_serie=kapital_serie)

    # --- TABS ---
    tab_names = [
        t("tab_chart", L),
        t("tab_growth", L),
        t("tab_balance", L),
        t("tab_profit", L),
        t("tab_drawdown", L),
        f'{t("tab_margin", L)}',
    ]
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(tab_names)

    # ===================== TAB 1: CHART (Portfolio Value) =====================
    with tab1:
        if wartosci_serie is not None and len(wartosci_serie) > 1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=wartosci_serie.index, y=wartosci_serie.values,
                mode="lines", name=t("portfolio_value_label", L),
                line=dict(color=chart_line_color, width=2.5),
                fill="tozeroy", fillcolor=hex_to_rgba(chart_line_color, 0.08),
                hovertemplate="<b>%{x|%b %d, '%y}</b><br>$%{y:,.2f}<extra></extra>",
            ))
            # Dotted reference line at start value
            fig.add_hline(y=wartosci_serie.iloc[0], line_dash="dot",
                          line_color="rgba(128,128,128,0.3)", line_width=1)
            fig.update_layout(**layout_base,
                xaxis=dict(showgrid=False, title="", gridcolor=grid_col),
                yaxis=dict(showgrid=True, gridcolor=grid_col, title="$",
                           tickprefix="$", separatethousands=True),
                showlegend=True, legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"))
            st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        else:
            st.info(t("no_data_for_tab", L))

    # ===================== TAB 2: GROWTH (cumulative %) =====================
    with tab2:
        if not roi_df.empty and len(roi_df) > 1:
            growth = pd.Series(roi_df["ROI (%)"].values, index=pd.to_datetime(roi_df["Data"]))
            fig = go.Figure()
            kolor_g = "#10b981" if growth.iloc[-1] >= 0 else "#ef4444"
            fig.add_trace(go.Scatter(
                x=growth.index, y=growth.values,
                mode="lines", name=t("tab_growth", L),
                line=dict(color=kolor_g, width=2.5),
                fill="tozeroy", fillcolor=hex_to_rgba(kolor_g, 0.08),
                hovertemplate="<b>%{x|%b %d, '%y}</b><br>%{y:+.2f}%<extra></extra>",
            ))

            # --- Benchmark overlay ---
            bench_colors = {"S&P 500": "#3b82f6", "WIG20": "#f59e0b"}
            bm_c1, bm_c2 = st.columns(2)
            with bm_c1:
                show_sp = st.checkbox("S&P 500", value=True, key="bench_sp500")
            with bm_c2:
                show_wig = st.checkbox("WIG20", value=True, key="bench_wig20")

            for bm_name, bm_ticker in _BENCHMARKS.items():
                show = show_sp if bm_name == "S&P 500" else show_wig
                if show:
                    bm_growth = pobierz_benchmark_growth(
                        bm_ticker, growth.index[0], growth.index[-1] + timedelta(days=1)
                    )
                    if not bm_growth.empty:
                        fig.add_trace(go.Scatter(
                            x=bm_growth.index, y=bm_growth.values,
                            mode="lines", name=bm_name,
                            line=dict(color=bench_colors[bm_name], width=1.5, dash="dash"),
                            hovertemplate=f"<b>{bm_name}</b><br>" + "%{x|%b %d, '%y}<br>%{y:+.2f}%<extra></extra>",
                        ))

            fig.add_hline(y=0, line_dash="dash", line_color="rgba(128,128,128,0.4)", line_width=1)
            # Endpoint annotation
            fig.add_annotation(
                x=growth.index[-1], y=growth.iloc[-1],
                text=f"<b>{growth.iloc[-1]:+.2f}%</b>",
                showarrow=True, arrowhead=2, arrowcolor=kolor_g,
                bgcolor=kolor_g, font=dict(color="white", size=11),
                bordercolor=kolor_g, borderwidth=1, borderpad=4, ax=40, ay=-25)
            fig.update_layout(**layout_base,
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor=grid_col, title="%",
                           zeroline=True, zerolinecolor="rgba(128,128,128,0.4)"),
                showlegend=True, legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"))
            st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        else:
            st.info(t("no_data_for_tab", L))

    # ===================== TAB 3: BALANCE (invested vs value) =====================
    with tab3:
        if wartosci_serie is not None and kapital_serie is not None and len(wartosci_serie) > 1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=wartosci_serie.index, y=kapital_serie.values,
                mode="lines", name=t("invested", L),
                line=dict(color="#64748b", width=1.5, dash="dot"),
                hovertemplate="<b>%{x|%b %d, '%y}</b><br>" + t("invested", L) + ": $%{y:,.2f}<extra></extra>",
            ))
            fig.add_trace(go.Scatter(
                x=wartosci_serie.index, y=wartosci_serie.values,
                mode="lines", name=t("portfolio_value_label", L),
                line=dict(color=chart_line_color, width=2.5),
                fill="tonexty", fillcolor=hex_to_rgba(chart_line_color, 0.06),
                hovertemplate="<b>%{x|%b %d, '%y}</b><br>" + t("portfolio_value_label", L) + ": $%{y:,.2f}<extra></extra>",
            ))
            fig.update_layout(**layout_base,
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor=grid_col, title="$", tickprefix="$"),
                showlegend=True, legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"))
            st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        else:
            st.info(t("no_data_for_tab", L))

    # ===================== TAB 4: PROFIT (P&L over time) =====================
    with tab4:
        if wartosci_serie is not None and kapital_serie is not None and len(wartosci_serie) > 1:
            profit = oblicz_profit_serie(wartosci_serie, kapital_serie)
            fig = go.Figure()
            kolor_p = "#10b981" if profit.iloc[-1] >= 0 else "#ef4444"
            fig.add_trace(go.Scatter(
                x=profit.index, y=profit.values,
                mode="lines", name=t("tab_profit", L),
                line=dict(color=kolor_p, width=2.5),
                fill="tozeroy", fillcolor=hex_to_rgba(kolor_p, 0.08),
                hovertemplate="<b>%{x|%b %d, '%y}</b><br>$%{y:+,.2f}<extra></extra>",
            ))
            fig.add_hline(y=0, line_dash="dash", line_color="rgba(128,128,128,0.4)", line_width=1)
            # Endpoint
            fig.add_annotation(
                x=profit.index[-1], y=profit.iloc[-1],
                text=f"<b>${profit.iloc[-1]:+,.2f}</b>",
                showarrow=True, arrowhead=2, arrowcolor=kolor_p,
                bgcolor=kolor_p, font=dict(color="white", size=11),
                bordercolor=kolor_p, borderwidth=1, borderpad=4, ax=50, ay=-25)
            fig.update_layout(**layout_base,
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor=grid_col, title="$",
                           zeroline=True, zerolinecolor="rgba(128,128,128,0.4)"),
                showlegend=True, legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"))
            st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        else:
            st.info(t("no_data_for_tab", L))

    # ===================== TAB 5: DRAWDOWN =====================
    with tab5:
        if wartosci_serie is not None and len(wartosci_serie) > 1:
            dd = oblicz_drawdown_serie(wartosci_serie)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=dd.index, y=dd.values,
                mode="lines", name=t("tab_drawdown", L),
                line=dict(color="#ef4444", width=2),
                fill="tozeroy", fillcolor="rgba(239,68,68,0.12)",
                hovertemplate="<b>%{x|%b %d, '%y}</b><br>%{y:.2f}%<extra></extra>",
            ))
            fig.add_hline(y=0, line_dash="solid", line_color="rgba(128,128,128,0.3)", line_width=1)
            # Max drawdown annotation
            if len(dd) > 0:
                max_dd_idx = dd.idxmin()
                max_dd_val = dd.min()
                fig.add_annotation(
                    x=max_dd_idx, y=max_dd_val,
                    text=f"<b>{max_dd_val:.2f}%</b>",
                    showarrow=True, arrowhead=2, arrowcolor="#ef4444",
                    bgcolor="#ef4444", font=dict(color="white", size=11),
                    bordercolor="#ef4444", borderwidth=1, borderpad=4, ax=40, ay=-25)
            fig.update_layout(**layout_base,
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor=grid_col, title="%", autorange=True),
                showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        else:
            st.info(t("no_data_for_tab", L))

    # ===================== TAB 6: MARGIN (Cash vs Invested) =====================
    with tab6:
        st.markdown(f'<span class="new-badge">{t("margin_new_badge", L)}</span>', unsafe_allow_html=True)
        if wartosci_serie is not None and kapital_serie is not None and len(wartosci_serie) > 1:
            # Margin = (Value - Invested) / Value * 100
            margin_pct = ((wartosci_serie - kapital_serie) / wartosci_serie) * 100
            margin_pct = margin_pct.fillna(0)
            fig = go.Figure()
            kolor_m = "#10b981" if margin_pct.iloc[-1] >= 0 else "#ef4444"
            fig.add_trace(go.Scatter(
                x=margin_pct.index, y=margin_pct.values,
                mode="lines", name="Margin %",
                line=dict(color=kolor_m, width=2.5),
                fill="tozeroy", fillcolor=hex_to_rgba(kolor_m, 0.06),
                hovertemplate="<b>%{x|%b %d, '%y}</b><br>%{y:+.2f}%<extra></extra>",
            ))
            fig.add_hline(y=0, line_dash="dash", line_color="rgba(128,128,128,0.4)", line_width=1)
            fig.add_annotation(
                x=margin_pct.index[-1], y=margin_pct.iloc[-1],
                text=f"<b>{margin_pct.iloc[-1]:+.2f}%</b>",
                showarrow=True, arrowhead=2, arrowcolor=kolor_m,
                bgcolor=kolor_m, font=dict(color="white", size=11),
                bordercolor=kolor_m, borderwidth=1, borderpad=4, ax=40, ay=-25)
            fig.update_layout(**layout_base,
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor=grid_col, title="%",
                           zeroline=True, zerolinecolor="rgba(128,128,128,0.4)"),
                showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        else:
            st.info(t("no_data_for_tab", L))

    # =========================================================================
    # STATISTICS PANEL — QUANT + DESIGNER
    # =========================================================================
    if stats:
        st.markdown(f'<div class="stat-table"><div class="stat-table-title">{t("statistics_title", L)}</div>', unsafe_allow_html=True)

        def _stat_class(val, invert=False):
            """Zwraca klasę CSS na podstawie wartości."""
            if isinstance(val, (int, float)):
                if invert:
                    return "negative" if val > 0 else ("positive" if val < 0 else "neutral")
                return "positive" if val > 0 else ("negative" if val < 0 else "neutral")
            return "neutral"

        def _fmt(val, suffix="%", decimals=2):
            """Formatuje wartość z sufiksem."""
            if isinstance(val, int):
                return f"{val}"
            return f"{val:+.{decimals}f}{suffix}" if suffix == "%" else f"{val:.{decimals}f}"

        # Lewy i prawy blok statystyk
        stat_left = [
            (t("stat_return", L), stats["return"], "%", False),
            (t("stat_annualised_return", L), stats["annualised_return"], "%", False),
            (t("stat_max_drawdown", L), stats["max_drawdown"], "%", False),
            (t("stat_daily_stdev", L), stats["daily_stdev"], "%", False),
            (t("stat_annualised_vol", L), stats["annualised_vol"], "%", False),
            (t("stat_sharpe", L), stats["sharpe"], "", False),
        ]
        stat_right = [
            (t("stat_sortino", L), stats["sortino"], "", False),
            (t("stat_skewness", L), stats["skewness"], "", False),
            (t("stat_kurtosis", L), stats["kurtosis"], "", False),
            (t("stat_ath_quote", L), stats["ath_quote"], "", False),
            (t("stat_days_since_ath", L), stats["days_since_ath"], "", False),
            (t("stat_return_since_ath", L), stats["return_since_ath"], "%", False),
        ]

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            rows_html = ""
            for label, val, suf, inv in stat_left:
                css_cl = _stat_class(val, inv)
                formatted = _fmt(val, suf)
                rows_html += f'<div class="stat-row"><span class="stat-label">{label}</span><span class="stat-val {css_cl}">{formatted}</span></div>'
            st.markdown(rows_html, unsafe_allow_html=True)
        with col_s2:
            rows_html = ""
            for label, val, suf, inv in stat_right:
                css_cl = _stat_class(val, inv)
                formatted = _fmt(val, suf)
                rows_html += f'<div class="stat-row"><span class="stat-label">{label}</span><span class="stat-val {css_cl}">{formatted}</span></div>'
            st.markdown(rows_html, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # --- TABELA PODSUMOWANIE ---
    st.markdown(f'<div class="section-header">{t("summary", L)}</div>', unsafe_allow_html=True)

    # --- Logo column for ticker table ---
    logo_col_html = []
    for tk in portfel_df["Ticker"]:
        logo = get_logo_html(tk, size=20)
        logo_col_html.append(f'{logo}{tk}')
    portfel_df_display = portfel_df.copy()
    # Show logos above the dataframe as a visual row
    logos_row = " ".join(f'<span class="logo-ticker">{get_logo_html(tk, 22)}<b>{tk}</b></span>&nbsp;&nbsp;' for tk in portfel_df["Ticker"])
    st.markdown(f'<div style="margin-bottom:8px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;">{logos_row}</div>', unsafe_allow_html=True)

    def kol_w(val):
        try:
            v = float(val)
            if v > 0: return "color:#00C853;font-weight:600"
            elif v < 0: return "color:#FF1744;font-weight:600"
        except: pass
        return ""
    styled = portfel_df.style.applymap(kol_w, subset=["Zysk/Strata ($)", "ROI (%)", "Zmienność (%)"]).format({
        "Ilość": "{:.4f}", "Śr. Cena Zakupu ($)": "${:,.2f}", "Cena Bieżąca ($)": "${:,.2f}",
        "Wartość ($)": "${:,.2f}", "Zysk/Strata ($)": "{:+,.2f}$", "ROI (%)": "{:+.2f}%", "Zmienność (%)": "{:+.2f}%"})
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # --- ALOKACJA + ZMIENNOŚĆ ---
    ch1, ch2 = st.columns([3, 1])
    with ch1:
        st.markdown(f'<div class="section-header">{t("allocation", L)}</div>', unsafe_allow_html=True)
        fig_pie = px.pie(portfel_df, values="Wartość ($)", names="Ticker", color_discrete_sequence=paleta, hole=0.4)
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        fig_pie.update_layout(**{**layout_base, "height": 350}, legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_pie, use_container_width=True, config=CHART_CONFIG)
    with ch2:
        st.markdown(f'<div class="section-header">{t("daily_volatility", L)}</div>', unsafe_allow_html=True)
        n_tickers = len(portfel_df)
        vol_height = max(80, min(32 * n_tickers + 30, 250))
        colors_vol = ["#10b981" if v >= 0 else "#ef4444" for v in portfel_df["Zmienność (%)"]]
        fig_vol = go.Figure(go.Bar(
            y=portfel_df["Ticker"], x=portfel_df["Zmienność (%)"],
            orientation="h", marker_color=colors_vol,
            marker_line_width=0, width=0.35,
            text=[f" {v:+.1f}% " for v in portfel_df["Zmienność (%)"]],
            textposition="outside", textfont=dict(size=9),
        ))
        fig_vol.update_layout(
            **{**layout_base, "height": vol_height, "margin": dict(t=5, b=5, l=50, r=35)},
            xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.08)", title="", zeroline=True,
                       zerolinecolor="rgba(128,128,128,0.3)", tickfont=dict(size=8)),
            yaxis=dict(showgrid=False, tickfont=dict(size=9), automargin=True),
            bargap=0.4,
        )
        st.plotly_chart(fig_vol, use_container_width=True, config=CHART_CONFIG)

    st.markdown("---")
    st.markdown(f'<p style="text-align:center;color:#64748b;font-size:0.75rem;font-weight:500;">'
        f'Portfel inwestycyjny · Yahoo Finance · {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>',
        unsafe_allow_html=True)

if __name__ == "__main__":
    main()
