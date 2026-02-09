# =============================================================================
# statistics.py — Advanced Financial Statistics Engine
# Agent QUANT — Sharpe, Sortino, Max DD, Skewness, Kurtosis, ATH
# =============================================================================

import numpy as np
import pandas as pd
from datetime import datetime


def oblicz_statystyki(wartosci_portfela: pd.Series, risk_free_rate: float = 0.05) -> dict:
    """
    Oblicza zaawansowane statystyki finansowe z serii wartości portfela.

    Args:
        wartosci_portfela: pd.Series z indeksem dat i wartościami portfela ($)
        risk_free_rate: roczna stopa wolna od ryzyka (domyślnie 5% — US T-bills)

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

    # --- Dzienne zwroty ---
    dzienne_zwroty = wartosci.pct_change().dropna()
    if len(dzienne_zwroty) < 1:
        return _puste_statystyki()

    # --- 1. Total Return ---
    total_return = (wartosci.iloc[-1] / wartosci.iloc[0] - 1) * 100

    # --- 2. Annualised Return (CAGR) ---
    n_days = (wartosci.index[-1] - wartosci.index[0]).days
    if n_days > 0:
        cagr = ((wartosci.iloc[-1] / wartosci.iloc[0]) ** (365.25 / n_days) - 1) * 100
    else:
        cagr = 0.0

    # --- 3. Max Drawdown ---
    cummax = wartosci.cummax()
    drawdown = (wartosci - cummax) / cummax * 100
    max_drawdown = drawdown.min()

    # --- 4. Daily STDEV ---
    daily_stdev = dzienne_zwroty.std() * 100

    # --- 5. Annualised Volatility ---
    ann_vol = dzienne_zwroty.std() * np.sqrt(252) * 100

    # --- 6. Sharpe Ratio ---
    excess_return = cagr / 100 - risk_free_rate
    sharpe = excess_return / (ann_vol / 100) if ann_vol > 0 else 0.0

    # --- 7. Sortino Ratio ---
    downside = dzienne_zwroty[dzienne_zwroty < 0]
    if len(downside) > 0:
        downside_dev = downside.std() * np.sqrt(252)
        sortino = excess_return / downside_dev if downside_dev > 0 else 0.0
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
