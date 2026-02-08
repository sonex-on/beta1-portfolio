# =============================================================================
# BETA1 — Portfolio Tracker v2 (Cloud Edition)
# Streamlit + Firebase Auth + Firestore + yfinance + Plotly
# Waluta: GBP (£) | Rynki: US, GPW, UK, Krypto Top 10
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

# =============================================================================
# STAŁE
# =============================================================================
APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(APP_DIR, "assets", "logo.jpg")

CRYPTO_TICKERS = {
    "Bitcoin (BTC)": "BTC-GBP", "Ethereum (ETH)": "ETH-GBP",
    "BNB": "BNB-GBP", "XRP": "XRP-GBP", "Cardano (ADA)": "ADA-GBP",
    "Solana (SOL)": "SOL-GBP", "Dogecoin (DOGE)": "DOGE-GBP",
    "Polkadot (DOT)": "DOT-GBP", "Avalanche (AVAX)": "AVAX-GBP",
    "Polygon (MATIC)": "POL-GBP",
}

MARKET_EXAMPLES = {
    "🇺🇸 US": "np. AAPL, MSFT, TSLA", "🇵🇱 GPW": "np. CDR.WA, PKN.WA",
    "🇬🇧 UK": "np. VOD.L, BARC.L", "🪙 Krypto": "np. BTC-GBP, ETH-GBP",
}

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
        tlo, tlo_k, tekst, ramka, tlo_sb = "#0E1117", "#1E2130", "#FAFAFA", "#2D3250", "#161B22"
    else:
        tlo, tlo_k, tekst, ramka, tlo_sb = "#FFFFFF", "#F8F9FA", "#1A1A2E", "#DEE2E6", "#F0F2F6"

    st.markdown(f"""<style>
    .stApp {{ background-color: {tlo}; color: {tekst}; }}
    section[data-testid="stSidebar"] {{ background-color: {tlo_sb}; }}
    .metric-card {{
        background: linear-gradient(135deg, {k1}22, {k2}22);
        border: 1px solid {ramka}; border-radius: 16px;
        padding: 20px 24px; text-align: center;
        transition: transform 0.2s, box-shadow 0.2s;
    }}
    .metric-card:hover {{ transform: translateY(-4px); box-shadow: 0 8px 25px {k1}33; }}
    .metric-card .value {{ font-size: 2rem; font-weight: 700; color: {k1}; margin: 8px 0 4px; }}
    .metric-card .label {{ font-size: 0.85rem; color: {tekst}AA; text-transform: uppercase; letter-spacing: 1px; }}
    .delta-positive {{ color: #00C853; }} .delta-negative {{ color: #FF1744; }}
    .app-title {{ text-align:center; font-size:1.8rem; font-weight:800;
        background: linear-gradient(90deg, {k1}, {k2});
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom:5px; }}
    .app-subtitle {{ text-align:center; font-size:0.9rem; color:{tekst}88; margin-bottom:20px; }}
    .section-header {{ font-size:1.2rem; font-weight:700; color:{k1};
        border-bottom:2px solid {k1}44; padding-bottom:8px; margin:30px 0 15px; }}
    .auth-container {{ max-width:400px; margin:60px auto; padding:40px;
        background:{tlo_k}; border-radius:20px; border:1px solid {ramka}; }}
    .logo-center {{ display:flex; justify-content:center; margin:10px 0 20px; }}
    </style>""", unsafe_allow_html=True)

# =============================================================================
# WALIDACJA
# =============================================================================
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
            "Śr. Cena Zakupu (£)": round(srednia_cena, 2), "Cena Bieżąca (£)": round(cena_akt, 2),
            "Wartość (£)": round(wartosc, 2), "Zysk/Strata (£)": round(zysk, 2),
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
        wartosci.append({"Data": data_idx, "Wartość Portfela (£)": round(wartosc_dnia, 2)})
    return pd.DataFrame(wartosci)

# =============================================================================
# EKRAN LOGOWANIA / REJESTRACJI
# =============================================================================
def ekran_autentykacji():
    """Wyświetla formularz logowania lub rejestracji. Zwraca True jeśli zalogowany."""
    if st.session_state.get("zalogowany"):
        return True

    zastosuj_motyw(True, "Oceanic")

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        # Logo
        if os.path.exists(LOGO_PATH):
            st.markdown('<div class="logo-center">', unsafe_allow_html=True)
            st.image(LOGO_PATH, width=120)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<p class="app-title">beta1</p>', unsafe_allow_html=True)
        st.markdown('<p class="app-subtitle">Portfolio Tracker — Zaloguj się</p>', unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["🔑 Logowanie", "📝 Rejestracja"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="twoj@email.com")
                haslo = st.text_input("Hasło", type="password")
                zapamietaj = st.checkbox("🔒 Zapamiętaj mnie")
                zaloguj = st.form_submit_button("Zaloguj się", use_container_width=True)

                if zaloguj:
                    if not email or not haslo:
                        st.error("Wypełnij wszystkie pola!")
                    else:
                        with st.spinner("Logowanie..."):
                            wynik = zaloguj_uzytkownika(email.strip(), haslo)
                        if wynik.get("error"):
                            st.error(f"❌ {wynik['error']}")
                        else:
                            st.session_state.zalogowany = True
                            st.session_state.uid = wynik["uid"]
                            st.session_state.email = wynik["email"]
                            st.session_state.id_token = wynik["id_token"]
                            st.success("✅ Zalogowano!")
                            st.rerun()

        with tab_register:
            with st.form("register_form"):
                reg_email = st.text_input("Email", placeholder="twoj@email.com", key="reg_email")
                reg_haslo = st.text_input("Hasło (min. 6 znaków)", type="password", key="reg_pass")
                reg_haslo2 = st.text_input("Powtórz hasło", type="password", key="reg_pass2")
                zarejestruj = st.form_submit_button("Zarejestruj się", use_container_width=True)

                if zarejestruj:
                    if not reg_email or not reg_haslo:
                        st.error("Wypełnij wszystkie pola!")
                    elif reg_haslo != reg_haslo2:
                        st.error("Hasła nie są identyczne!")
                    elif len(reg_haslo) < 6:
                        st.error("Hasło musi mieć min. 6 znaków!")
                    else:
                        with st.spinner("Rejestracja..."):
                            wynik = zarejestruj_uzytkownika(reg_email.strip(), reg_haslo)
                        if wynik.get("error"):
                            st.error(f"❌ {wynik['error']}")
                        else:
                            # Zapisz profil w Firestore
                            db = inicjalizuj_firebase()
                            zapisz_profil(db, wynik["uid"], wynik["email"])
                            st.session_state.zalogowany = True
                            st.session_state.uid = wynik["uid"]
                            st.session_state.email = wynik["email"]
                            st.session_state.id_token = wynik["id_token"]
                            st.success("✅ Konto utworzone! Witaj w beta1!")
                            st.rerun()
    return False

# =============================================================================
# GŁÓWNA APLIKACJA
# =============================================================================
def main():
    st.set_page_config(page_title="beta1 — Portfolio Tracker", page_icon="📊",
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

    # =========================================================================
    # SIDEBAR
    # =========================================================================
    with st.sidebar:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=100)
        st.markdown('<p class="app-title">beta1</p>', unsafe_allow_html=True)
        st.caption(f"👤 {st.session_state.email}")

        if st.button("🚪 Wyloguj", use_container_width=True):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

        # --- Motywy ---
        st.markdown("---")
        st.session_state.motyw_ciemny = st.toggle("🌙 Tryb Ciemny", value=st.session_state.motyw_ciemny)
        st.session_state.paleta = st.selectbox("🎨 Paleta", list(PALETY_KOLOROW.keys()),
            index=list(PALETY_KOLOROW.keys()).index(st.session_state.paleta))
        kolory_html = " ".join(f'<span style="display:inline-block;width:18px;height:18px;'
            f'border-radius:50%;background:{c};margin:2px;"></span>' for c in PALETY_KOLOROW[st.session_state.paleta])
        st.markdown(kolory_html, unsafe_allow_html=True)

        # --- Zarządzanie portfelami ---
        st.markdown("---")
        st.markdown("📁 **Portfele** (max 3)")
        portfele = pobierz_portfele(db, uid)

        # Utwórz domyślny portfel jeśli brak
        if not portfele:
            stworz_portfel(db, uid, "Mój Portfel")
            portfele = pobierz_portfele(db, uid)

        # Wybór aktywnego portfela
        nazwy = [p["nazwa"] for p in portfele]
        ids = [p["id"] for p in portfele]
        if st.session_state.aktywny_portfel not in ids:
            st.session_state.aktywny_portfel = ids[0] if ids else None

        wybrany_idx = ids.index(st.session_state.aktywny_portfel) if st.session_state.aktywny_portfel in ids else 0
        wybrany = st.selectbox("Aktywny portfel", nazwy, index=wybrany_idx, key="portfel_select")
        st.session_state.aktywny_portfel = ids[nazwy.index(wybrany)]

        # Nowy portfel
        col_np1, col_np2 = st.columns([3, 1])
        with col_np1:
            nowa_nazwa = st.text_input("Nowy portfel", placeholder="Nazwa", label_visibility="collapsed")
        with col_np2:
            if st.button("➕", key="btn_nowy_portfel"):
                if nowa_nazwa.strip():
                    wyn = stworz_portfel(db, uid, nowa_nazwa.strip())
                    if wyn.get("error"): st.error(wyn["error"])
                    else: st.success(f"✅ '{nowa_nazwa}' utworzony!"); st.rerun()

        # Usuwanie portfela
        if len(portfele) > 1:
            if st.button("🗑️ Usuń aktywny portfel", key="btn_usun_portfel"):
                usun_portfel(db, uid, st.session_state.aktywny_portfel)
                st.session_state.aktywny_portfel = None
                st.rerun()

        # --- Formularz transakcji ---
        st.markdown("---")
        st.markdown("📝 **Dodaj Transakcję**")

        with st.expander("📌 Przykłady tickerów"):
            for rynek, ex in MARKET_EXAMPLES.items(): st.caption(f"{rynek}: {ex}")

        with st.expander("🪙 Krypto Top 10"):
            krypto_sel = st.selectbox("Kryptowaluta", ["--"] + list(CRYPTO_TICKERS.keys()), key="krypto_s")

        with st.form("form_tx", clear_on_submit=True):
            domyslny = CRYPTO_TICKERS.get(krypto_sel, "") if krypto_sel != "--" else ""
            ticker_in = st.text_input("Ticker", value=domyslny, placeholder="np. AAPL")
            typ = st.radio("Typ", ["Kupno", "Sprzedaż"], horizontal=True)
            ilosc = st.number_input("Ilość", min_value=0.0001, value=1.0, step=0.1, format="%.4f")
            cena = st.number_input("Cena zakupu (£)", min_value=0.01, value=100.0, step=0.01, format="%.2f")
            data_tx = st.date_input("Data", value=date.today())
            dodaj = st.form_submit_button("➕ Dodaj", use_container_width=True)

            if dodaj and st.session_state.aktywny_portfel:
                tk = waliduj_ticker(ticker_in)
                il, cn = waliduj_liczbe(ilosc), waliduj_liczbe(cena)
                if not tk: st.error("❌ Nieprawidłowy ticker.")
                elif il <= 0: st.error("❌ Ilość > 0!")
                elif cn <= 0: st.error("❌ Cena > 0!")
                else:
                    if typ == "Sprzedaż":
                        trans = pobierz_transakcje(db, uid, st.session_state.aktywny_portfel)
                        posiadane = sum(float(t["ilosc"]) if t["typ"]=="Kupno" else -float(t["ilosc"])
                                        for t in trans if t["ticker"] == tk)
                        if il > posiadane:
                            st.error(f"❌ Masz tylko {posiadane:.4f} {tk}"); st.stop()
                    dodaj_transakcje(db, uid, st.session_state.aktywny_portfel,
                        {"ticker": tk, "ilosc": il, "cena_zakupu": cn, "data": str(data_tx), "typ": typ})
                    st.success(f"✅ {typ}: {il}× {tk} @ £{cn:.2f}")
                    st.rerun()

        # Lista transakcji
        st.markdown("---")
        st.markdown("🗂️ **Transakcje**")
        if st.session_state.aktywny_portfel:
            transakcje = pobierz_transakcje(db, uid, st.session_state.aktywny_portfel)
            if transakcje:
                for t in transakcje:
                    emoji = "🟢" if t["typ"] == "Kupno" else "🔴"
                    c1, c2 = st.columns([4, 1])
                    with c1: st.caption(f"{emoji} {t['typ']}: {t['ilosc']}× {t['ticker']} @ £{float(t['cena_zakupu']):.2f}")
                    with c2:
                        if st.button("🗑️", key=f"del_{t['id']}"):
                            usun_transakcje(db, uid, st.session_state.aktywny_portfel, t["id"])
                            st.rerun()
            else:
                st.info("Brak transakcji. Dodaj pierwszą! ☝️")

    # =========================================================================
    # ZASTOSUJ MOTYW
    # =========================================================================
    zastosuj_motyw(st.session_state.motyw_ciemny, st.session_state.paleta)
    paleta = PALETY_KOLOROW[st.session_state.paleta]

    # =========================================================================
    # DASHBOARD
    # =========================================================================
    st.markdown('<p class="app-title">📊 beta1 — Portfolio Tracker</p>', unsafe_allow_html=True)
    st.markdown('<p class="app-subtitle">Dane z opóźnieniem ~15 min | Waluta: GBP (£)</p>', unsafe_allow_html=True)

    if not st.session_state.aktywny_portfel:
        st.warning("Utwórz portfel w panelu bocznym."); return

    transakcje = pobierz_transakcje(db, uid, st.session_state.aktywny_portfel)
    if not transakcje:
        st.markdown("### 👋 Witaj! Dodaj transakcję w panelu bocznym.")
        return

    with st.spinner("📡 Pobieram dane rynkowe..."):
        portfel_df = oblicz_portfel(transakcje)

    if portfel_df.empty:
        st.warning("⚠️ Brak aktywnych pozycji."); return

    # --- METRIC CARDS ---
    lw = portfel_df["Wartość (£)"].sum()
    lk = (portfel_df["Śr. Cena Zakupu (£)"] * portfel_df["Ilość"]).sum()
    lz = lw - lk
    lr = ((lw - lk) / lk * 100) if lk > 0 else 0
    kz = "delta-positive" if lz >= 0 else "delta-negative"
    zn = "+" if lz >= 0 else ""

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="label">Wartość Portfela</div>'
            f'<div class="value">£{lw:,.2f}</div>'
            f'<div style="color:{paleta[2]}">Zainwestowano: £{lk:,.2f}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="label">Zysk / Strata</div>'
            f'<div class="value {kz}">{zn}£{lz:,.2f}</div>'
            f'<div class="{kz}">{zn}{lr:.2f}%</div></div>', unsafe_allow_html=True)
    with c3:
        najl = portfel_df.loc[portfel_df["ROI (%)"].idxmax()]
        st.markdown(f'<div class="metric-card"><div class="label">Najlepsza Pozycja</div>'
            f'<div class="value">{najl["Ticker"]}</div>'
            f'<div class="delta-positive">ROI: {najl["ROI (%)"]:.2f}%</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- TABELA ---
    st.markdown('<div class="section-header">📋 Podsumowanie</div>', unsafe_allow_html=True)
    def kol_w(val):
        try:
            v = float(val)
            if v > 0: return "color:#00C853;font-weight:600"
            elif v < 0: return "color:#FF1744;font-weight:600"
        except: pass
        return ""
    styled = portfel_df.style.applymap(kol_w, subset=["Zysk/Strata (£)", "ROI (%)", "Zmienność (%)"]).format({
        "Ilość": "{:.4f}", "Śr. Cena Zakupu (£)": "£{:,.2f}", "Cena Bieżąca (£)": "£{:,.2f}",
        "Wartość (£)": "£{:,.2f}", "Zysk/Strata (£)": "{:+,.2f}£", "ROI (%)": "{:+.2f}%", "Zmienność (%)": "{:+.2f}%"})
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # --- WYKRESY ---
    is_dark = st.session_state.motyw_ciemny
    font_col = "#FAFAFA" if is_dark else "#1A1A2E"
    layout_base = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       font=dict(color=font_col), margin=dict(t=20, b=20, l=20, r=20), height=400)

    ch1, ch2 = st.columns(2)
    with ch1:
        st.markdown('<div class="section-header">🥧 Alokacja</div>', unsafe_allow_html=True)
        fig_pie = px.pie(portfel_df, values="Wartość (£)", names="Ticker", color_discrete_sequence=paleta, hole=0.4)
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        fig_pie.update_layout(**layout_base, legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_pie, use_container_width=True)
    with ch2:
        st.markdown('<div class="section-header">📊 Zysk/Strata</div>', unsafe_allow_html=True)
        colors_bar = ["#00C853" if v >= 0 else "#FF1744" for v in portfel_df["Zysk/Strata (£)"]]
        fig_bar = go.Figure(go.Bar(x=portfel_df["Ticker"], y=portfel_df["Zysk/Strata (£)"], marker_color=colors_bar))
        fig_bar.update_layout(**layout_base, xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.2)", title="£"))
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- HISTORIA ---
    st.markdown('<div class="section-header">📈 Wartość w Czasie</div>', unsafe_allow_html=True)
    with st.spinner("📊 Generuję historię..."):
        hist_df = oblicz_historie_portfela(transakcje)
    if not hist_df.empty:
        fig_line = px.area(hist_df, x="Data", y="Wartość Portfela (£)", color_discrete_sequence=[paleta[0]])
        fig_line.update_traces(fill="tozeroy", fillcolor=f"{paleta[0]}22", line=dict(width=2.5))
        fig_line.update_layout(**layout_base, xaxis=dict(showgrid=False, title=""),
            yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.2)", title="£"))
        st.plotly_chart(fig_line, use_container_width=True)

    # --- ZMIENNOŚĆ ---
    st.markdown('<div class="section-header">📉 Zmienność Dzienna</div>', unsafe_allow_html=True)
    colors_vol = ["#00C853" if v >= 0 else "#FF1744" for v in portfel_df["Zmienność (%)"]]
    fig_vol = go.Figure(go.Bar(x=portfel_df["Ticker"], y=portfel_df["Zmienność (%)"], marker_color=colors_vol))
    fig_vol.update_layout(**{**layout_base, "height": 300}, xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.2)", title="%"))
    st.plotly_chart(fig_vol, use_container_width=True)

    st.markdown("---")
    st.markdown(f'<p style="text-align:center;color:#888;font-size:0.8rem;">'
        f'beta1 Portfolio Tracker | Yahoo Finance | {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>',
        unsafe_allow_html=True)

if __name__ == "__main__":
    main()
