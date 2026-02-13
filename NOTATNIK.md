# 📓 NOTATNIK PROJEKTU — Portfel Inwestycyjny

> **Zasada:** Czytam ten plik na początku każdej sesji. Zapisuję tu planowane zadania i usuwam je po implementacji.

---

## 🏗️ Architektura

| Plik | Opis |
|------|------|
| `app.py` | Główna aplikacja Streamlit (~1760 linii) |
| `statistics.py` | Silnik statystyk: Sharpe, Sortino, Max DD, Skewness, Kurtosis |
| `translations.py` | I18n — PL + EN, funkcja `t(key, lang)` |
| `ocr_reader.py` | OCR import z Gemini Vision API |
| `requirements.txt` | Zależności pip |

**Stack:** Streamlit · Firebase/Firestore · yfinance · Plotly · Google Gemini Vision  
**Deploy:** Streamlit Cloud → `beta1-portfolio.streamlit.app`  
**Repo:** `github.com/sonex-on/beta1-portfolio`

---

## ✅ Zaimplementowane funkcje

### Core

- Dashboard z metric cards (wartość, profit, ROI%, best/worst stock)
- Transakcje (kupno/sprzedaż) z walidacją + formularz
- Multi-portfel (tworzenie/usuwanie/przełączanie)
- Autentykacja Firebase (Google login)
- Ciemny/jasny motyw
- Język PL/EN

### Wykresy (Chart tabs)

- **Chart** — linia cenowa portfela
- **Growth** — ROI% (poprawiony — nie liczy depozytów jako zysk)
- **Balance** — wartość portfela w $
- **Profit** — zysk/strata dzienna
- **Drawdown** — max drawdown %
- **Margin** — marża handlowa
- **Benchmark** — overlay S&P 500 + WIG20 (przerywane linie + checkboxy)

### Navbar tabs

1. **Transakcje** — formularz + lista z 💡 notatkami
2. **Import** — OCR (upload/camera) + CSV (XTB, eToro, IBKR, Generic)
3. **Dywidendy** — yield, last div, roczny dochód
4. **Kalendarz** — wyszukiwarka spółek + earnings/ex-div + cena/MC/sektor
5. **Korelacja** — heatmap + wykres cenowy, multiselect, slider 30-365 dni
6. **Indykatory** — candlestick + SMA/EMA/Bollinger/RSI/MACD/Volume, timeframe 1D-1Y
7. **Ustawienia** — motyw, język

### Statystyki

- Zwrot/Zwrot roczny — poprawiony (`(wartość - zainwestowane) / zainwestowane`)
- Sharpe, Sortino, Max Drawdown, Skewness, Kurtosis, ATH

### Inne

- Pie chart sektorowy (pod metric cards)
- Notatki do transakcji (💡 tooltip)
- Logo spółek (pobierane z logo.clearbit.com)

---

## 📋 Do zrobienia (backlog)

_(Tutaj zapisuję zadania na przyszłe sesje — usuwam po implementacji)_

- _(brak zaplanowanych zadań)_

---

## 🐛 Znane problemy

- Kalendarz: yfinance `.calendar` bywa pusty dla mniejszych spółek — używamy `.earnings_dates` + `.info`
- Polski rynek: nie wszystkie tickery `.WA` mają pełne dane w yfinance

---

_Ostatnia aktualizacja: 2026-02-10_
