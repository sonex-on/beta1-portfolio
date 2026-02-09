# =============================================================================
# ocr_reader.py — Agent 1: VISION — Gemini Vision OCR for XTB Screenshots
# Extracts portfolio transactions from XTB trading platform screenshots
# using Google Gemini 2.0 Flash Vision API.
# =============================================================================

import json
import re
import streamlit as st
from datetime import date

# Lazy import — google.genai installed via google-genai package
_genai_client = None


def _get_client():
    """Lazy-init Gemini client with API key from secrets."""
    global _genai_client
    if _genai_client is None:
        from google import genai
        api_key = None
        # 1) st.secrets
        try:
            api_key = st.secrets.get("gemini_api_key")
        except Exception:
            pass
        if not api_key:
            raise ValueError("Brak klucza Gemini API! Dodaj gemini_api_key do streamlit_secrets.toml")
        _genai_client = genai.Client(api_key=api_key)
    return _genai_client


# ─────────────────────────────────────────────────────────────────────────────
# Prompt engineered specifically for XTB platform screenshots
# ─────────────────────────────────────────────────────────────────────────────
_EXTRACTION_PROMPT = """You are an expert financial data extractor. Analyze this screenshot from the XTB trading platform and extract ALL visible transactions/positions.

For EACH transaction or position you find, extract:
1. **ticker** — the stock ticker symbol (e.g. AAPL, TSLA, CDR). 
   - If only the company name is visible (e.g. "Apple Inc."), convert it to the standard ticker.
   - For Polish stocks, add ".WA" suffix (e.g. CDR.WA, PKO.WA).
   - For crypto, use format like BTC-USD, ETH-USD.
2. **quantity** (ilość) — number of shares/units. Must be > 0.
3. **price** (cena) — purchase price per unit in the original currency. Convert to USD if possible.
4. **date** — transaction date in YYYY-MM-DD format. If not visible, use today's date.
5. **type** — "Kupno" (buy) or "Sprzedaż" (sell). If showing open positions, assume "Kupno".

IMPORTANT RULES:
- Extract ALL rows/positions visible in the screenshot.
- If you see a portfolio summary, extract each stock as a separate entry.
- Numbers may use comma as decimal separator (European format: 1.234,56 = 1234.56).
- If price is in PLN or EUR, keep the original price value.
- If date is not clearly visible, use "{today}" as the date.
- If you cannot determine if it's buy or sell, default to "Kupno".

Return ONLY a valid JSON array. Each element must have exactly these keys:
{{"ticker": "...", "quantity": ..., "price": ..., "date": "YYYY-MM-DD", "type": "Kupno" or "Sprzedaż"}}

If you cannot find ANY transaction data in the image, return an empty array: []

RESPOND WITH ONLY THE JSON ARRAY, NO OTHER TEXT."""


def extract_transactions_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> list[dict]:
    """
    Send image to Gemini Vision API and extract transaction data.
    
    Args:
        image_bytes: Raw bytes of the uploaded image
        mime_type: MIME type of the image (image/jpeg, image/png, image/webp)
    
    Returns:
        List of dicts with keys: ticker, ilosc, cena_zakupu, data, typ
        Empty list if no transactions found or on error.
    """
    client = _get_client()
    
    today_str = date.today().isoformat()
    prompt = _EXTRACTION_PROMPT.replace("{today}", today_str)
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"inline_data": {"mime_type": mime_type, "data": image_bytes}},
                        {"text": prompt},
                    ],
                }
            ],
        )
        
        raw_text = response.text.strip()
        
        # Clean response — remove markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
            raw_text = re.sub(r"\s*```\s*$", "", raw_text)
        
        transactions_raw = json.loads(raw_text)
        
        if not isinstance(transactions_raw, list):
            return []
        
        # Normalize to our internal format
        results = []
        for tx in transactions_raw:
            try:
                ticker = str(tx.get("ticker", "")).strip().upper()
                quantity = float(tx.get("quantity", 0))
                price = float(tx.get("price", 0))
                tx_date = str(tx.get("date", today_str)).strip()
                tx_type = str(tx.get("type", "Kupno")).strip()
                
                # Validate minimum requirements
                if not ticker or quantity <= 0 or price <= 0:
                    continue
                
                # Normalize type
                if tx_type.lower() in ("kupno", "buy", "long"):
                    tx_type = "Kupno"
                elif tx_type.lower() in ("sprzedaż", "sprzedaz", "sell", "short"):
                    tx_type = "Sprzedaż"
                else:
                    tx_type = "Kupno"
                
                # Validate date format
                try:
                    parts = tx_date.split("-")
                    if len(parts) != 3 or len(parts[0]) != 4:
                        tx_date = today_str
                except Exception:
                    tx_date = today_str
                
                results.append({
                    "ticker": ticker,
                    "ilosc": round(quantity, 4),
                    "cena_zakupu": round(price, 2),
                    "data": tx_date,
                    "typ": tx_type,
                })
            except (ValueError, TypeError, KeyError):
                continue
        
        return results
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini zwróciło nieprawidłowy JSON: {str(e)[:200]}")
    except Exception as e:
        error_msg = str(e)[:300]
        if "429" in error_msg or "RATE_LIMIT" in error_msg.upper():
            raise ConnectionError("Rate limit Gemini API. Poczekaj chwilę i spróbuj ponownie.")
        raise RuntimeError(f"Błąd Gemini API: {error_msg}")
