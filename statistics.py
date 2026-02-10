# =============================================================================
# statistics.py — Advanced Financial Statistics Engine
# Agent QUANT — Sharpe, Sortino, Max DD, Skewness, Kurtosis, ATH
# =============================================================================

import numpy as np
import pandas as pd
from datetime import datetime


def oblicz_statystyki(wartosci_portfela: pd.Series, risk_free_rate: float = 0.05, kapital_serie: pd.Series = None) -> dict:
    """
    Oblicza zaawansowane statystyki finansowe z serii wartości portfela.

    Args:
        wartosci_portfela: pd.Series z indeksem dat i wartościami portfela ($)
        risk_free_rate: roczna stopa wolna od ryzyka (domyślnie 5% — US T-bills)
        kapital_serie: pd.Series z zainwestowanym kapitałem (opcjonalnie)

    Returns:
        dict z 12 metrykami finansowymi
    """
    if wartosci_portfela is None or len(wartosci_portfela) < 2:
        return _puste_statystyki()

    # Usuń NaN i zera
    wartosci = wartosci_portfela.dropna()
    wartosci = wartosci[wartosci > 0]
    if len(wartosci) < 2:
        return _puste_statystyki()

    # --- Dzienne zwroty (z filtrowaniem outlierów) ---
    dzienne_zwroty = wartosci.pct_change().dropna()
    # Filtruj ekstremalnie duże zwroty (>50% dziennie = błąd danych)
    dzienne_zwroty = dzienne_zwroty[(dzienne_zwroty > -0.5) & (dzienne_zwroty < 0.5)]
    if len(dzienne_zwroty) < 1:
        return _puste_statystyki()

    # --- Ile dni ma portfel ---
    n_days = (wartosci.index[-1] - wartosci.index[0]).days
    wystarczajaco_dlugi = n_days >= 60  # Min 60 dni do annualizacji

    # --- 1. Total Return (based on invested capital if available) ---
    if kapital_serie is not None and len(kapital_serie) > 0:
        kapital_total = kapital_serie.iloc[-1]
        if kapital_total > 0:
            total_return = (wartosci.iloc[-1] / kapital_total - 1) * 100
        else:
            total_return = 0.0
    else:
        total_return = (wartosci.iloc[-1] / wartosci.iloc[0] - 1) * 100

    # --- 2. Annualised Return (CAGR) — tylko dla portfeli > 60 dni ---
    if wystarczajaco_dlugi and n_days > 0:
        if kapital_serie is not None and len(kapital_serie) > 0:
            kapital_total = kapital_serie.iloc[-1]
            if kapital_total > 0:
                cagr = ((wartosci.iloc[-1] / kapital_total) ** (365.25 / n_days) - 1) * 100
            else:
                cagr = 0.0
        else:
            cagr = ((wartosci.iloc[-1] / wartosci.iloc[0]) ** (365.25 / n_days) - 1) * 100
        # Ogranicz do rozsądnych wartości
        cagr = max(-99.99, min(cagr, 9999.99))
    else:
        cagr = total_return  # Dla krótkich portfeli = po prostu total return

    # --- 3. Max Drawdown ---
    cummax = wartosci.cummax()
    drawdown = (wartosci - cummax) / cummax * 100
    max_drawdown = drawdown.min()

    # --- 4. Daily STDEV ---
    daily_stdev = dzienne_zwroty.std() * 100

    # --- 5. Annualised Volatility ---
    if wystarczajaco_dlugi:
        ann_vol = dzienne_zwroty.std() * np.sqrt(252) * 100
    else:
        ann_vol = daily_stdev  # Nie annualizuj dla krótkich portfeli

    # --- 6. Sharpe Ratio ---
    if wystarczajaco_dlugi and ann_vol > 0:
        excess_return = cagr / 100 - risk_free_rate
        sharpe = excess_return / (ann_vol / 100)
        sharpe = max(-10.0, min(sharpe, 10.0))  # Ogranicz do [-10, 10]
    else:
        sharpe = 0.0

    # --- 7. Sortino Ratio ---
    downside = dzienne_zwroty[dzienne_zwroty < 0]
    if wystarczajaco_dlugi and len(downside) > 0:
        downside_dev = downside.std() * np.sqrt(252)
        excess_return = cagr / 100 - risk_free_rate
        sortino = excess_return / downside_dev if downside_dev > 0 else 0.0
        sortino = max(-10.0, min(sortino, 10.0))
    else:
        sortino = 0.0

    # --- 8. Skewness ---
    skewness = float(dzienne_zwroty.skew()) if len(dzienne_zwroty) > 2 else 0.0

    # --- 9. Kurtosis ---
    kurtosis = float(dzienne_zwroty.kurtosis()) if len(dzienne_zwroty) > 3 else 0.0

    # --- 10. ATH Quote ---
    ath_value = wartosci.max()
    ath_quote = (wartosci.iloc[-1] / ath_value) * 100 if ath_value > 0 else 0.0

    # --- 11. Days since ATH ---
    ath_date = wartosci.idxmax()
    days_since_ath = (wartosci.index[-1] - ath_date).days

    # --- 12. Return since ATH ---
    return_since_ath = (wartosci.iloc[-1] / ath_value - 1) * 100 if ath_value > 0 else 0.0

    return {
        "return": round(total_return, 2),
        "annualised_return": round(cagr, 2),
        "max_drawdown": round(max_drawdown, 2),
        "daily_stdev": round(daily_stdev, 2),
        "annualised_vol": round(ann_vol, 2),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "skewness": round(skewness, 2),
        "kurtosis": round(kurtosis, 2),
        "ath_quote": round(ath_quote, 2),
        "days_since_ath": int(days_since_ath),
        "return_since_ath": round(return_since_ath, 2),
    }


def oblicz_drawdown_serie(wartosci_portfela: pd.Series) -> pd.Series:
    """Zwraca serię drawdown (%) w czasie."""
    if wartosci_portfela is None or len(wartosci_portfela) < 2:
        return pd.Series(dtype=float)
    cummax = wartosci_portfela.cummax()
    return ((wartosci_portfela - cummax) / cummax) * 100


def oblicz_growth_serie(wartosci_portfela: pd.Series) -> pd.Series:
    """Zwraca serię skumulowanego wzrostu (%) od początku."""
    if wartosci_portfela is None or len(wartosci_portfela) < 2:
        return pd.Series(dtype=float)
    return ((wartosci_portfela / wartosci_portfela.iloc[0]) - 1) * 100


def oblicz_profit_serie(wartosci_portfela: pd.Series, kapital: pd.Series) -> pd.Series:
    """Zwraca serię profit/loss ($) w czasie."""
    if wartosci_portfela is None or kapital is None:
        return pd.Series(dtype=float)
    return wartosci_portfela - kapital


def _puste_statystyki() -> dict:
    """Zwraca pusty zestaw statystyk."""
    return {
        "return": 0.0, "annualised_return": 0.0, "max_drawdown": 0.0,
        "daily_stdev": 0.0, "annualised_vol": 0.0, "sharpe": 0.0,
        "sortino": 0.0, "skewness": 0.0, "kurtosis": 0.0,
        "ath_quote": 0.0, "days_since_ath": 0, "return_since_ath": 0.0,
    }
