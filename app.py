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
    tab_tx, tab_ocr, tab_cfg = st.tabs([
        t("nav_transactions", L), t("nav_ocr_import", L), t("nav_settings", L)
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
                    dodaj_transakcje(db, uid, st.session_state.aktywny_portfel,
                        {"ticker": tk, "ilosc": il, "cena_zakupu": cn, "data": str(data_tx), "typ": typ_db})
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
                    tc1, tc2 = st.columns([4, 1])
                    with tc1: st.caption(f"{emoji} {typ_display}: {tx['ilosc']}× {tx['ticker']} @ ${float(tx['cena_zakupu']):.2f}")
                    with tc2:
                        if st.button("🗑️", key=f"del_{tx['id']}"):
                            usun_transakcje(db, uid, st.session_state.aktywny_portfel, tx["id"])
                            st.rerun()
            else:
                st.info(t("no_transactions", L))

    with tab_ocr:
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
        margin=dict(t=20, b=40, l=50, r=30), height=420,
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
        stats = oblicz_statystyki(wartosci_serie)

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
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(t("no_data_for_tab", L))

    # ===================== TAB 2: GROWTH (cumulative %) =====================
    with tab2:
        if wartosci_serie is not None and len(wartosci_serie) > 1:
            growth = oblicz_growth_serie(wartosci_serie)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
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
        st.plotly_chart(fig_pie, use_container_width=True)
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
        st.plotly_chart(fig_vol, use_container_width=True)

    st.markdown("---")
    st.markdown(f'<p style="text-align:center;color:#64748b;font-size:0.75rem;font-weight:500;">'
        f'Portfel inwestycyjny · Yahoo Finance · {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>',
        unsafe_allow_html=True)

if __name__ == "__main__":
    main()
