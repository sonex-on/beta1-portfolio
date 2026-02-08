# =============================================================================
# firebase_config.py — Moduł Firebase dla beta1 Portfolio Tracker
# Firebase Auth (REST API) + Firestore (firebase-admin SDK)
# =============================================================================

import streamlit as st
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# =============================================================================
# INICJALIZACJA FIREBASE
# =============================================================================

def inicjalizuj_firebase():
    """
    Inicjalizuje Firebase Admin SDK.
    Konfiguracja pobierana z st.secrets (Streamlit Cloud) lub pliku lokalnego.
    """
    if not firebase_admin._apps:
        try:
            # Próba 1: st.secrets (dla Streamlit Cloud)
            cred_dict = dict(st.secrets["firebase_service_account"])
            cred = credentials.Certificate(cred_dict)
        except (KeyError, FileNotFoundError):
            try:
                # Próba 2: plik lokalny
                cred = credentials.Certificate("firebase_service_account.json")
            except Exception as e:
                st.error(f"❌ Brak konfiguracji Firebase! Dodaj plik firebase_service_account.json")
                st.stop()
        firebase_admin.initialize_app(cred)
    return firestore.client()

def pobierz_api_key():
    """Pobiera Firebase Web API Key z konfiguracji."""
    try:
        return st.secrets["firebase_web_api_key"]
    except KeyError:
        try:
            with open("firebase_web_config.json", "r") as f:
                config = json.load(f)
                return config["apiKey"]
        except Exception:
            st.error("❌ Brak Firebase Web API Key!")
            st.stop()

# =============================================================================
# AUTENTYKACJA — Firebase Auth REST API
# =============================================================================

AUTH_BASE_URL = "https://identitytoolkit.googleapis.com/v1/accounts"

def zarejestruj_uzytkownika(email: str, haslo: str) -> dict:
    """
    Rejestruje nowego użytkownika w Firebase Auth.
    Zwraca dict z uid, email, idToken lub error.
    """
    api_key = pobierz_api_key()
    url = f"{AUTH_BASE_URL}:signUp?key={api_key}"
    payload = {"email": email, "password": haslo, "returnSecureToken": True}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if "error" in data:
            msg = data["error"].get("message", "Nieznany błąd")
            errors_pl = {
                "EMAIL_EXISTS": "Ten email jest już zarejestrowany.",
                "WEAK_PASSWORD": "Hasło za słabe (min. 6 znaków).",
                "INVALID_EMAIL": "Nieprawidłowy format email.",
            }
            return {"error": errors_pl.get(msg, msg)}
        return {
            "uid": data["localId"],
            "email": data["email"],
            "id_token": data["idToken"],
            "refresh_token": data["refreshToken"],
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Błąd połączenia: {str(e)[:100]}"}

def zaloguj_uzytkownika(email: str, haslo: str) -> dict:
    """
    Loguje użytkownika w Firebase Auth.
    Zwraca dict z uid, email, idToken lub error.
    """
    api_key = pobierz_api_key()
    url = f"{AUTH_BASE_URL}:signInWithPassword?key={api_key}"
    payload = {"email": email, "password": haslo, "returnSecureToken": True}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if "error" in data:
            msg = data["error"].get("message", "Nieznany błąd")
            errors_pl = {
                "EMAIL_NOT_FOUND": "Nie znaleziono konta z tym emailem.",
                "INVALID_PASSWORD": "Nieprawidłowe hasło.",
                "USER_DISABLED": "Konto zostało zablokowane.",
                "INVALID_LOGIN_CREDENTIALS": "Nieprawidłowy email lub hasło.",
            }
            return {"error": errors_pl.get(msg, msg)}
        return {
            "uid": data["localId"],
            "email": data["email"],
            "id_token": data["idToken"],
            "refresh_token": data["refreshToken"],
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Błąd połączenia: {str(e)[:100]}"}

# =============================================================================
# FIRESTORE — CRUD PORTFELI I TRANSAKCJI
# =============================================================================

def pobierz_portfele(db, uid: str) -> list:
    """Pobiera listę portfeli użytkownika (max 3)."""
    portfele = []
    docs = db.collection("users").document(uid).collection("portfolios").stream()
    for doc in docs:
        dane = doc.to_dict()
        dane["id"] = doc.id
        portfele.append(dane)
    return portfele

def stworz_portfel(db, uid: str, nazwa: str) -> dict:
    """Tworzy nowy portfel. Sprawdza limit 3 portfeli."""
    istniejace = pobierz_portfele(db, uid)
    if len(istniejace) >= 3:
        return {"error": "Osiągnięto limit 3 portfeli!"}

    # Sprawdź unikalność nazwy
    for p in istniejace:
        if p.get("nazwa", "").lower() == nazwa.lower():
            return {"error": f"Portfel '{nazwa}' już istnieje!"}

    ref = db.collection("users").document(uid).collection("portfolios").document()
    dane = {"nazwa": nazwa, "utworzony": datetime.now().isoformat()}
    ref.set(dane)
    return {"id": ref.id, "nazwa": nazwa}

def usun_portfel(db, uid: str, portfolio_id: str):
    """Usuwa portfel i wszystkie jego transakcje."""
    # Usuń transakcje
    trans_ref = (db.collection("users").document(uid)
                 .collection("portfolios").document(portfolio_id)
                 .collection("transactions"))
    for doc in trans_ref.stream():
        doc.reference.delete()
    # Usuń portfel
    db.collection("users").document(uid).collection("portfolios").document(portfolio_id).delete()

def pobierz_transakcje(db, uid: str, portfolio_id: str) -> list:
    """Pobiera wszystkie transakcje z danego portfela."""
    transakcje = []
    docs = (db.collection("users").document(uid)
            .collection("portfolios").document(portfolio_id)
            .collection("transactions")
            .order_by("data")
            .stream())
    for doc in docs:
        dane = doc.to_dict()
        dane["id"] = doc.id
        transakcje.append(dane)
    return transakcje

def dodaj_transakcje(db, uid: str, portfolio_id: str, transakcja: dict) -> str:
    """Dodaje nową transakcję do portfela. Zwraca ID dokumentu."""
    ref = (db.collection("users").document(uid)
           .collection("portfolios").document(portfolio_id)
           .collection("transactions").document())
    transakcja["utworzony"] = datetime.now().isoformat()
    ref.set(transakcja)
    return ref.id

def usun_transakcje(db, uid: str, portfolio_id: str, transaction_id: str):
    """Usuwa transakcję z portfela."""
    (db.collection("users").document(uid)
     .collection("portfolios").document(portfolio_id)
     .collection("transactions").document(transaction_id)
     .delete())

def zapisz_profil(db, uid: str, email: str):
    """Zapisuje/aktualizuje profil użytkownika w Firestore."""
    ref = db.collection("users").document(uid)
    if not ref.get().exists:
        ref.set({
            "email": email,
            "utworzony": datetime.now().isoformat(),
        })
