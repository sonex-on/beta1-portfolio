# =============================================================================
# logo_fetcher.py — Agent 3: LOGO MASTER — Company Logo Fetcher
# Fetches original company logos for tickers using yfinance + Clearbit fallback.
# =============================================================================

import streamlit as st
import requests

# Cache for logo URLs — persisted in session_state to survive reruns
_LOGO_CACHE_KEY = "_logo_cache"

# Placeholder SVG for when no logo is found (simple building icon)
_PLACEHOLDER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" '
    'stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/>'
    '<path d="M9 22V12h6v10"/><path d="M8 6h.01"/><path d="M16 6h.01"/>'
    '<path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M8 10h.01"/>'
    '<path d="M16 10h.01"/></svg>'
)


def _get_cache() -> dict:
    """Get or initialize logo cache in session state."""
    if _LOGO_CACHE_KEY not in st.session_state:
        st.session_state[_LOGO_CACHE_KEY] = {}
    return st.session_state[_LOGO_CACHE_KEY]


def get_logo_url(ticker: str) -> str | None:
    """
    Get logo URL for a ticker symbol.
    
    Strategy:
    1. Check session cache
    2. Try yfinance info['logo_url'] or info['website'] → clearbit
    3. Try Clearbit Logo API directly (domain guess)
    4. Return None if all fail
    
    Args:
        ticker: Stock ticker symbol (e.g. AAPL, CDR.WA, BTC-USD)
    
    Returns:
        URL string to the logo image, or None if not found.
    """
    cache = _get_cache()
    
    # Check cache first
    if ticker in cache:
        return cache[ticker]
    
    logo_url = None
    
    # Strategy 1: yfinance info
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        
        # Direct logo URL (some tickers have it)
        logo_url = info.get("logo_url")
        
        # If no direct logo, try website → clearbit
        if not logo_url:
            website = info.get("website", "")
            if website:
                # Extract domain from website URL
                domain = website.replace("https://", "").replace("http://", "").split("/")[0]
                clearbit_url = f"https://logo.clearbit.com/{domain}"
                # Verify the logo actually exists
                try:
                    resp = requests.head(clearbit_url, timeout=3, allow_redirects=True)
                    if resp.status_code == 200:
                        logo_url = clearbit_url
                except Exception:
                    pass
    except Exception:
        pass
    
    # Strategy 2: Direct clearbit guess for well-known domains
    if not logo_url:
        domain_guesses = _guess_domain(ticker)
        for domain in domain_guesses:
            try:
                clearbit_url = f"https://logo.clearbit.com/{domain}"
                resp = requests.head(clearbit_url, timeout=3, allow_redirects=True)
                if resp.status_code == 200:
                    logo_url = clearbit_url
                    break
            except Exception:
                continue
    
    # Cache the result (even None to avoid re-fetching)
    cache[ticker] = logo_url
    return logo_url


def _guess_domain(ticker: str) -> list[str]:
    """
    Guess company domain from ticker for Clearbit logo lookup.
    Returns list of possible domains to try.
    """
    # Known domain mappings for popular tickers
    KNOWN_DOMAINS = {
        "AAPL": ["apple.com"],
        "MSFT": ["microsoft.com"],
        "GOOGL": ["google.com"],
        "GOOG": ["google.com"],
        "AMZN": ["amazon.com"],
        "TSLA": ["tesla.com"],
        "META": ["meta.com"],
        "NVDA": ["nvidia.com"],
        "NFLX": ["netflix.com"],
        "INTC": ["intel.com"],
        "AMD": ["amd.com"],
        "PYPL": ["paypal.com"],
        "ADBE": ["adobe.com"],
        "CRM": ["salesforce.com"],
        "CSCO": ["cisco.com"],
        "ORCL": ["oracle.com"],
        "IBM": ["ibm.com"],
        "V": ["visa.com"],
        "MA": ["mastercard.com"],
        "JPM": ["jpmorganchase.com"],
        "BAC": ["bankofamerica.com"],
        "DIS": ["disney.com"],
        "KO": ["coca-cola.com"],
        "PEP": ["pepsico.com"],
        "NKE": ["nike.com"],
        "WMT": ["walmart.com"],
        "BA": ["boeing.com"],
        "XOM": ["exxonmobil.com"],
        "JNJ": ["jnj.com"],
        "PFE": ["pfizer.com"],
        "MRNA": ["modernatx.com"],
        "SPOT": ["spotify.com"],
        # Polish stocks
        "CDR.WA": ["cdprojektred.com"],
        "PKO.WA": ["pkobp.pl"],
        "PZU.WA": ["pzu.pl"],
        "KGH.WA": ["kghm.com"],
        "PEO.WA": ["pekao.com.pl"],
        "DNP.WA": ["dinoposka.pl"],
        "LPP.WA": ["lppsa.com"],
        "ALE.WA": ["allegro.pl"],
        "JSW.WA": ["jsw.pl"],
        # Crypto — use logos from major crypto sites
        "BTC-USD": ["bitcoin.org"],
        "ETH-USD": ["ethereum.org"],
        "SOL-USD": ["solana.com"],
        "ADA-USD": ["cardano.org"],
        "XRP-USD": ["ripple.com"],
        "DOGE-USD": ["dogecoin.com"],
        "DOT-USD": ["polkadot.network"],
        "AVAX-USD": ["avax.network"],
        "MATIC-USD": ["polygon.technology"],
        "LINK-USD": ["chain.link"],
    }
    
    # Clean ticker
    base_ticker = ticker.upper().strip()
    if base_ticker in KNOWN_DOMAINS:
        return KNOWN_DOMAINS[base_ticker]
    
    # Generic guesses
    base = base_ticker.replace(".WA", "").replace("-USD", "").lower()
    return [f"{base}.com", f"{base}.io"]


def get_logo_html(ticker: str, size: int = 22) -> str:
    """
    Get HTML <img> tag for ticker logo, or fallback SVG placeholder.
    
    Args:
        ticker: Stock ticker symbol
        size: Logo size in pixels (default 22)
    
    Returns:
        HTML string with <img> or <span> containing SVG placeholder
    """
    url = get_logo_url(ticker)
    if url:
        return (
            f'<img src="{url}" width="{size}" height="{size}" '
            f'style="border-radius:4px;vertical-align:middle;margin-right:6px;'
            f'object-fit:contain;background:#fff;" '
            f'onerror="this.style.display=\'none\'" />'
        )
    else:
        return (
            f'<span style="display:inline-flex;align-items:center;justify-content:center;'
            f'width:{size}px;height:{size}px;border-radius:4px;background:rgba(100,116,139,0.15);'
            f'color:#94a3b8;margin-right:6px;vertical-align:middle;font-size:{size-6}px;">'
            f'{ticker[:2]}</span>'
        )
