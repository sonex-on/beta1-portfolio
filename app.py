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
)
from ticker_db import TICKER_DATABASE, szukaj_tickery
from translations import t

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
    """Aplikuje CSS motywu + paletę kolorów."""
    paleta = PALETY_KOLOROW.get(paleta_nazwa, PALETY_KOLOROW["Oceanic"])
    k1, k2 = paleta[0], paleta[1]
    if ciemny:
        tlo, tlo_k, tekst, ramka, tlo_sb = "#0a0e17", "#111827", "#F1F5F9", "#1e293b", "#0f1520"
        card_bg = "rgba(17,24,39,0.7)"
        card_border = "rgba(255,255,255,0.06)"
        glass = "backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);"
    else:
        tlo, tlo_k, tekst, ramka, tlo_sb = "#f8fafc", "#ffffff", "#0f172a", "#e2e8f0", "#f1f5f9"
        card_bg = "rgba(255,255,255,0.8)"
        card_border = "rgba(0,0,0,0.06)"
        glass = "backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);"

    st.markdown(f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
    * {{ font-family: 'Inter', -apple-system, sans-serif !important; }}
    .stApp {{ background: {tlo}; color: {tekst}; }}
    section[data-testid="stSidebar"] {{ background: {tlo_sb}; border-right: 1px solid {card_border}; }}
    .metric-card {{
        background: {card_bg}; {glass}
        border: 1px solid {card_border}; border-radius: 16px;
        padding: 18px 20px; text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        transition: transform 0.25s cubic-bezier(.4,0,.2,1), box-shadow 0.25s;
    }}
    .metric-card:hover {{ transform: translateY(-3px); box-shadow: 0 12px 32px rgba(0,0,0,0.15); }}
    .metric-card .value {{ font-size: 1.7rem; font-weight: 800; color: {k1}; margin: 6px 0 3px; letter-spacing: -0.02em; }}
    .metric-card .label {{ font-size: 0.7rem; color: {tekst}99; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600; }}
    .metric-card .sub {{ font-size: 0.8rem; margin-top: 2px; }}
    .delta-positive {{ color: #10b981; }} .delta-negative {{ color: #ef4444; }}
    .app-title {{ text-align:center; font-size:2rem; font-weight:900; letter-spacing:-0.03em;
        background: linear-gradient(135deg, {k1}, {k2});
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom:2px; }}
    .app-subtitle {{ text-align:center; font-size:0.8rem; color:{tekst}66; margin-bottom:24px; font-weight:500; }}
    .section-header {{ font-size:1.05rem; font-weight:700; color:{k1};
        border-left:3px solid {k1}; padding-left:12px; margin:28px 0 12px; }}
    .loss-badge {{ display:inline-block; background:rgba(239,68,68,0.12); color:#ef4444;
        padding:3px 10px; border-radius:8px; font-size:0.75rem; font-weight:600; margin-top:4px; }}
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

    if tryb == t("auth_login", L):
        with st.form("login_form"):
            email = st.text_input(t("email", L), placeholder="your@email.com")
            haslo = st.text_input(t("password", L), type="password")
            zapamietaj = st.checkbox(t("remember_me", L))
            zaloguj = st.form_submit_button(t("login_btn", L), use_container_width=True)

            if zaloguj:
                if not email or not haslo:
                    st.error(t("fill_all", L))
                else:
                    with st.spinner(t("logging_in", L)):
                        wynik = zaloguj_uzytkownika(email.strip(), haslo)
                    if wynik.get("error"):
                        st.error(f"❌ {wynik['error']}")
                    else:
                        st.session_state.zalogowany = True
                        st.session_state.uid = wynik["uid"]
                        st.session_state.email = wynik["email"]
                        st.session_state.id_token = wynik["id_token"]
                        st.success(t("logged_in", L))
                        st.rerun()

    else:
        with st.form("register_form"):
            reg_email = st.text_input(t("email", L), placeholder="your@email.com")
            reg_haslo = st.text_input(t("password_min", L), type="password")
            reg_haslo2 = st.text_input(t("password_repeat", L), type="password")
            zarejestruj = st.form_submit_button(t("register_btn", L), use_container_width=True)

            if zarejestruj:
                if not reg_email or not reg_haslo:
                    st.error(t("fill_all", L))
                elif reg_haslo != reg_haslo2:
                    st.error(t("passwords_mismatch", L))
                elif len(reg_haslo) < 6:
                    st.error(t("password_too_short", L))
                else:
                    with st.spinner(t("registering", L)):
                        wynik = zarejestruj_uzytkownika(reg_email.strip(), reg_haslo)
                    if wynik.get("error"):
                        st.error(f"❌ {wynik['error']}")
                    else:
                        db = inicjalizuj_firebase()
                        zapisz_profil(db, wynik["uid"], wynik["email"])
                        st.session_state.zalogowany = True
                        st.session_state.uid = wynik["uid"]
                        st.session_state.email = wynik["email"]
                        st.session_state.id_token = wynik["id_token"]
                        st.success(t("account_created", L))
                        st.rerun()
    return False

# =============================================================================
# GŁÓWNA APLIKACJA
# =============================================================================
def main():
    st.set_page_config(page_title="Portfel inwestycyjny", page_icon="📊",
                       layout="wide", initial_sidebar_state="expanded")

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
    # SIDEBAR
    # =========================================================================
    with st.sidebar:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=100)
        st.markdown('<p class="app-title">Portfel inwestycyjny</p>', unsafe_allow_html=True)
        st.caption(f"👤 {st.session_state.email}")

        if st.button(t("logout", L), use_container_width=True):
            lang_backup = st.session_state.get("lang", "pl")
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.session_state.lang = lang_backup
            st.rerun()

        # --- Język ---
        st.markdown("---")
        lang_options = {"🇵🇱 Polski": "pl", "🇬🇧 English": "en"}
        lang_labels = list(lang_options.keys())
        current_idx = list(lang_options.values()).index(L) if L in lang_options.values() else 0
        wybrany_jezyk = st.radio(t("language", L), lang_labels, index=current_idx, horizontal=True, key="lang_main")
        new_lang = lang_options[wybrany_jezyk]
        if new_lang != st.session_state.lang:
            st.session_state.lang = new_lang
            st.rerun()
        L = st.session_state.lang

        # --- Motywy ---
        st.session_state.motyw_ciemny = st.toggle(t("dark_mode", L), value=st.session_state.motyw_ciemny)
        st.session_state.paleta = st.selectbox(t("palette", L), list(PALETY_KOLOROW.keys()),
            index=list(PALETY_KOLOROW.keys()).index(st.session_state.paleta))
        kolory_html = " ".join(f'<span style="display:inline-block;width:18px;height:18px;'
            f'border-radius:50%;background:{c};margin:2px;"></span>' for c in PALETY_KOLOROW[st.session_state.paleta])
        st.markdown(kolory_html, unsafe_allow_html=True)

        # --- Zarządzanie portfelami ---
        st.markdown("---")
        st.markdown(t("portfolios", L))
        portfele = pobierz_portfele(db, uid)

        if not portfele:
            default_name = "My Portfolio" if L == "en" else "Mój Portfel"
            stworz_portfel(db, uid, default_name)
            portfele = pobierz_portfele(db, uid)

        nazwy = [p["nazwa"] for p in portfele]
        ids = [p["id"] for p in portfele]
        if st.session_state.aktywny_portfel not in ids:
            st.session_state.aktywny_portfel = ids[0] if ids else None

        wybrany_idx = ids.index(st.session_state.aktywny_portfel) if st.session_state.aktywny_portfel in ids else 0
        wybrany = st.selectbox(t("active_portfolio", L), nazwy, index=wybrany_idx, key="portfel_select")
        st.session_state.aktywny_portfel = ids[nazwy.index(wybrany)]

        col_np1, col_np2 = st.columns([3, 1])
        with col_np1:
            nowa_nazwa = st.text_input(t("new_portfolio", L), placeholder=t("name_placeholder", L), label_visibility="collapsed")
        with col_np2:
            if st.button("➕", key="btn_nowy_portfel"):
                if nowa_nazwa.strip():
                    wyn = stworz_portfel(db, uid, nowa_nazwa.strip())
                    if wyn.get("error"): st.error(wyn["error"])
                    else: st.success(f"✅ '{nowa_nazwa}' {t('portfolio_created', L)}"); st.rerun()

        if len(portfele) > 1:
            if st.button(t("delete_portfolio", L), key="btn_usun_portfel"):
                usun_portfel(db, uid, st.session_state.aktywny_portfel)
                st.session_state.aktywny_portfel = None
                st.rerun()

        # --- Formularz transakcji ---
        st.markdown("---")
        st.markdown(t("add_transaction", L))

        opcje_tickerow = [t("type_manually", L)] + list(TICKER_DATABASE.keys())
        wybrany_ticker = st.selectbox(
            t("ticker_search", L), opcje_tickerow, index=0,
            key="ticker_search", help=t("ticker_search_help", L)
        )

        if wybrany_ticker != t("type_manually", L):
            ticker_z_bazy = TICKER_DATABASE.get(wybrany_ticker, "")
        else:
            ticker_z_bazy = ""

        buy_label = t("buy", L)
        sell_label = t("sell", L)
        with st.form("form_tx", clear_on_submit=True):
            ticker_in = st.text_input(t("ticker", L), value=ticker_z_bazy, placeholder="e.g. AAPL, CDR.WA, BTC-USD")
            typ = st.radio(t("type", L), [buy_label, sell_label], horizontal=True)
            ilosc = st.number_input(t("quantity", L), min_value=0.0001, value=1.0, step=0.1, format="%.4f")
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

        # Lista transakcji
        st.markdown("---")
        st.markdown(t("transactions", L))
        if st.session_state.aktywny_portfel:
            transakcje = pobierz_transakcje(db, uid, st.session_state.aktywny_portfel)
            if transakcje:
                for tx in transakcje:
                    emoji = "🟢" if tx["typ"] == "Kupno" else "🔴"
                    typ_display = t("buy", L) if tx["typ"] == "Kupno" else t("sell", L)
                    c1, c2 = st.columns([4, 1])
                    with c1: st.caption(f"{emoji} {typ_display}: {tx['ilosc']}× {tx['ticker']} @ ${float(tx['cena_zakupu']):.2f}")
                    with c2:
                        if st.button("🗑️", key=f"del_{tx['id']}"):
                            usun_transakcje(db, uid, st.session_state.aktywny_portfel, tx["id"])
                            st.rerun()
            else:
                st.info(t("no_transactions", L))

    # =========================================================================
    # ZASTOSUJ MOTYW
    # =========================================================================
    zastosuj_motyw(st.session_state.motyw_ciemny, st.session_state.paleta)
    paleta = PALETY_KOLOROW[st.session_state.paleta]

    # =========================================================================
    # DASHBOARD
    # =========================================================================
    st.markdown('<p class="app-title">📊 Portfel inwestycyjny</p>', unsafe_allow_html=True)
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

    # Dzienny P&L — użyj zmienności
    dzienny_pl = sum(portfel_df["Wartość ($)"] * portfel_df["Zmienność (%)"] / 100)
    dzienny_pct = (dzienny_pl / lw * 100) if lw > 0 else 0
    dz_kz = "delta-positive" if dzienny_pl >= 0 else "delta-negative"
    dz_zn = "+" if dzienny_pl >= 0 else ""

    # Najgorsza i najlepsza pozycja
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
            f'<div class="{"loss-badge" if ng_roi < 0 else "sub delta-positive"}">{"" if ng_roi < 0 else "+"}{(ng_roi if ng_roi < 0 else najlepszy["ROI (%)"]):.2f}%</div></div>', unsafe_allow_html=True)

    # --- TABELA ---
    st.markdown(f'<div class="section-header">{t("summary", L)}</div>', unsafe_allow_html=True)
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

    # --- WYKRESY ---
    is_dark = st.session_state.motyw_ciemny
    font_col = "#FAFAFA" if is_dark else "#1A1A2E"
    layout_base = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       font=dict(color=font_col), margin=dict(t=20, b=20, l=20, r=20), height=400)

    ch1, ch2 = st.columns(2)
    with ch1:
        st.markdown(f'<div class="section-header">{t("allocation", L)}</div>', unsafe_allow_html=True)
        fig_pie = px.pie(portfel_df, values="Wartość ($)", names="Ticker", color_discrete_sequence=paleta, hole=0.4)
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        fig_pie.update_layout(**layout_base, legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_pie, use_container_width=True)
    with ch2:
        st.markdown(f'<div class="section-header">{t("profit_loss_chart", L)}</div>', unsafe_allow_html=True)
        fig_pl = go.Figure()
        sorted_df = portfel_df.sort_values("Zysk/Strata ($)")
        colors_line = ["#10b981" if v >= 0 else "#ef4444" for v in sorted_df["Zysk/Strata ($)"]]
        fig_pl.add_trace(go.Scatter(
            x=sorted_df["Ticker"], y=sorted_df["Zysk/Strata ($)"],
            mode="lines+markers", name="P&L",
            line=dict(color=paleta[0], width=2.5),
            marker=dict(color=colors_line, size=10, line=dict(width=2, color="white")),
        ))
        fig_pl.add_hline(y=0, line_dash="dash", line_color="rgba(128,128,128,0.4)", line_width=1)
        fig_pl.update_layout(**{**layout_base, "height": 320},
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.1)", title="$"))
        st.plotly_chart(fig_pl, use_container_width=True)

    # --- HISTORIA ---
    st.markdown(f'<div class="section-header">{t("value_over_time", L)}</div>', unsafe_allow_html=True)
    with st.spinner(t("generating_history", L)):
        hist_df = oblicz_historie_portfela(transakcje)
    if not hist_df.empty:
        fig_line = px.area(hist_df, x="Data", y="Wartość Portfela ($)", color_discrete_sequence=[paleta[0]])
        fig_line.update_traces(fill="tozeroy", fillcolor=hex_to_rgba(paleta[0], 0.13), line=dict(width=2.5))
        fig_line.update_layout(**layout_base, xaxis=dict(showgrid=False, title=""),
            yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.2)", title="$"))
        st.plotly_chart(fig_line, use_container_width=True)

    # --- ZWROT Z KAPITAŁU (ROI%) ---
    st.markdown(f'<div class="section-header">{t("roi_title", L)}</div>', unsafe_allow_html=True)
    with st.spinner(t("calculating_roi", L)):
        roi_df = oblicz_roi_portfela(transakcje)
    if not roi_df.empty and len(roi_df) > 1:
        ostatni_roi = roi_df["ROI (%)"].iloc[-1]
        kolor_roi = "#00C853" if ostatni_roi >= 0 else "#FF1744"
        kolor_fill = hex_to_rgba("#00C853" if ostatni_roi >= 0 else "#FF1744", 0.1)

        fig_roi = go.Figure()
        fig_roi.add_hline(y=0, line_dash="dash", line_color="rgba(128,128,128,0.5)", line_width=1)
        fig_roi.add_trace(go.Scatter(
            x=roi_df["Data"], y=roi_df["ROI (%)"],
            mode="lines", name=t("your_portfolio", L),
            line=dict(color=kolor_roi, width=2.5),
            fill="tozeroy", fillcolor=kolor_fill,
        ))
        # Etykieta z aktualnym ROI% na końcu linii
        fig_roi.add_annotation(
            x=roi_df["Data"].iloc[-1], y=ostatni_roi,
            text=f"<b>{ostatni_roi:+.2f}%</b>",
            showarrow=True, arrowhead=2, arrowsize=1, arrowcolor=kolor_roi,
            bgcolor=kolor_roi, font=dict(color="white", size=12),
            bordercolor=kolor_roi, borderwidth=1, borderpad=4,
            ax=40, ay=-20
        )
        fig_roi.update_layout(
            **{**layout_base, "height": 350},
            xaxis=dict(showgrid=False, title=""),
            yaxis=dict(
                showgrid=True, gridcolor="rgba(128,128,128,0.2)",
                title=t("roi_ylabel", L), zeroline=True,
                zerolinecolor="rgba(128,128,128,0.5)", zerolinewidth=1
            ),
            showlegend=True, legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig_roi, use_container_width=True)

    # --- ZMIENNOŚĆ (ultra-compact horizontal) ---
    st.markdown(f'<div class="section-header">{t("daily_volatility", L)}</div>', unsafe_allow_html=True)
    n_tickers = len(portfel_df)
    vol_height = max(80, min(35 * n_tickers + 40, 200))
    colors_vol = ["#10b981" if v >= 0 else "#ef4444" for v in portfel_df["Zmienność (%)"]]
    fig_vol = go.Figure(go.Bar(
        y=portfel_df["Ticker"], x=portfel_df["Zmienność (%)"],
        orientation="h", marker_color=colors_vol,
        marker_line_width=0, width=0.4,
        text=[f" {v:+.1f}% " for v in portfel_df["Zmienność (%)"]],
        textposition="outside", textfont=dict(size=10),
    ))
    fig_vol.update_layout(
        **{**layout_base, "height": vol_height, "margin": dict(t=5, b=5, l=60, r=40)},
        xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.08)", title="", zeroline=True,
                   zerolinecolor="rgba(128,128,128,0.3)", tickfont=dict(size=9)),
        yaxis=dict(showgrid=False, tickfont=dict(size=10), automargin=True),
        bargap=0.4,
    )
    st.plotly_chart(fig_vol, use_container_width=True)

    st.markdown("---")
    st.markdown(f'<p style="text-align:center;color:#64748b;font-size:0.75rem;font-weight:500;">'
        f'Portfel inwestycyjny · Yahoo Finance · {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>',
        unsafe_allow_html=True)

if __name__ == "__main__":
    main()
