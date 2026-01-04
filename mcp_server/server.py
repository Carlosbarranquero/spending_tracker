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
    Registra un gasto con conversión automática a Euros.
    """
    
    sid = (spreadsheet_id or DEFAULT_SPREADSHEET_ID).strip()
    title = sheet_name or first_sheet_title(sid)
    
    # 1. Normalizar fecha y hora (ICT - Indochina)
    ict = pytz.timezone('Asia/Bangkok')
    now = datetime.now(ict)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    
    # 2. Validar y formatear monto original
    amt_raw = (amount or "").replace(",", ".")
    try:
        amt_float = float(amt_raw)
        if amt_float <= 0:
            return "❌ El monto debe ser mayor a 0"
    except ValueError:
        return f"❌ Monto inválido: {amt_raw}"

    # 3. Lógica de Conversión a EUR
    amount_eur = amt_float # Valor por defecto si ya es EUR
    
    if currency.upper() != "EUR":
        try:
            # Leer el factor de conversión de la hoja 'conversion' celda B2
            result = sheets().spreadsheets().values().get(
                spreadsheetId=sid,
                range="conversion!B2"
            ).execute()
            
            conv_values = result.get('values', [])
            if not conv_values or not conv_values[0]:
                return "❌ No se encontró el valor de conversión en 'conversion!B2'"
            
            conversion_rate = float(str(conv_values[0][0]).replace(",", "."))
            amount_eur = amt_float * conversion_rate
        except Exception as e:
            return f"❌ Error al obtener tasa de conversión: {str(e)}"

    # 4. Generar ID único
    receipt_id = generate_receipt_id(description, amt_raw, date_str + time_str)
    
    # 5. Estructurar fila (Añadida columna H: Amount EUR)
    values = [[
        date_str,       # A: date_str
        receipt_id,     # B: receipt_id
        description,    # C: description
        category,       # D: category
        amt_raw,        # E: amount
        currency,       # F: currency
        time_str,       # G: time_str
        round(amount_eur, 2) # H: Amount (Euros)
    ]]
    
    try:
        sheets().spreadsheets().values().append(
            spreadsheetId=sid,
            range=f"{title}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()
        
        return (
            f"✅ GASTO REGISTRADO CON ÉXITO\n"
            f"🆔 ID: {receipt_id}\n"
            f"💰 Original: {amt_raw} {currency}\n"
            f"💶 Total EUR: {round(amount_eur, 2)}€\n"
            f"📝 Concepto: {description}"
        )
    
    except Exception as e:
        return f"❌ Error al registrar en Google Sheets: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="streamable-http")