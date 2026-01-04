#!/usr/bin/env python3
import os
from datetime import datetime
from enum import Enum
import hashlib
import pytz

from google.oauth2 import service_account
from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP

PORT = int(os.environ.get("PORT", "3001"))
mcp = FastMCP("sheets-expense-advanced", host="0.0.0.0", port=PORT)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SA_JSON = os.environ.get("GSHEETS_SA_JSON", "service-account.json")
DEFAULT_SPREADSHEET_ID = os.environ.get("GSHEETS_DEFAULT_SPREADSHEET_ID","")


def sheets():
    creds = service_account.Credentials.from_service_account_file(SA_JSON, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)

def first_sheet_title(spreadsheet_id: str) -> str:
    meta = sheets().spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sh = (meta.get("sheets") or [])
    if not sh:
        raise RuntimeError("Spreadsheet has no sheets/tabs.")
    return sh[0]["properties"]["title"]

def generate_receipt_id(description: str, amount: str, timestamp: str) -> str:
    """Genera un ID único para cada gasto (identificador de recibo)"""
    combined = f"{description}{amount}{timestamp}"
    return hashlib.md5(combined.encode()).hexdigest()[:8].upper()

def calculate_tax_category(amount: float, category: str) -> str:
    """Determina si el gasto es deducible según categoría y monto"""
    tax_deductible = {
        "Alimentación": False,
        "Transporte": True,
        "Servicios": True,
        "Salud": True,
        "Educación": True,
        "Oficina": True,
        "Tecnología": True,
        "Viaje": True,
        "General": False,
    }
    return "Sí" if tax_deductible.get(category, False) else "No"
@mcp.tool()
async def add_expense(
    description: str,
    amount: str,
    category: str = "General",
    currency: str = "EUR",
    sheet_name: str = "",
    spreadsheet_id: str = "",
) -> str:
    """
    Registra un gasto con los campos esenciales.
    
    Campos almacenados:
    1. date_str: Fecha del registro (YYYY-MM-DD)
    2. receipt_id: Identificador único
    3. description: Detalle del gasto
    4. category: Categoría del gasto
    5. amount: Monto numérico
    6. currency: Divisa (USD/EUR/etc)
    7. time_str: Hora exacta
    """
    
    sid = (spreadsheet_id or DEFAULT_SPREADSHEET_ID).strip()
    title = sheet_name or first_sheet_title(sid)
    
    # 1. Normalizar fecha y hora (ICT - Indochina)
    ict = pytz.timezone('Asia/Bangkok')
    now = datetime.now(ict)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    
    # 2. Validar y formatear monto
    amt = (amount or "").replace(",", ".")
    try:
        amt_float = float(amt)
        if amt_float <= 0:
            return "❌ El monto debe ser mayor a 0"
    except ValueError:
        return f"❌ Monto inválido: {amt}"
    
    # 3. Generar ID único
    receipt_id = generate_receipt_id(description, amt, date_str + time_str)
    
    # 4. Estructurar fila (Únicamente los campos solicitados)
    values = [[
        date_str,      # A: date_str
        receipt_id,    # B: receipt_id
        description,   # C: description
        category,      # D: category
        amt,           # E: amount
        currency,      # F: currency
        time_str       # G: time_str
    ]]
    
    try:
        sheets().spreadsheets().values().append(
            spreadsheetId=sid,
            range=f"{title}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()
        
        return (
            f"✅ GASTO SIMPLIFICADO REGISTRADO\n"
            f"🆔 ID: {receipt_id}\n"
            f"📅 Fecha: {date_str} {time_str}\n"
            f"💰 Monto: {amt} {currency}\n"
            f"📝 Concepto: {description}\n"
            f"🏷️ Categoría: {category}"
        )
    
    except Exception as e:
        return f"❌ Error al registrar en Google Sheets: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="streamable-http")