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

class PaymentMethod(str, Enum):
    """Métodos de pago para auditoría financiera"""
    EFECTIVO = "Efectivo"
    TARJETA_CREDITO = "Tarjeta Crédito"
    TARJETA_DEBITO = "Tarjeta Débito"
    TRANSFERENCIA = "Transferencia"
    BILLETERA_DIGITAL = "Billetera Digital"
    OTRO = "Otro"

class ExpenseStatus(str, Enum):
    """Estado del gasto para seguimiento"""
    PENDIENTE = "Pendiente"
    CONFIRMADO = "Confirmado"
    REEMBOLSABLE = "Reembolsable"
    IMPUTABLE = "Imputable"

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
    currency: str = "USD",
    payment_method: str = "Tarjeta Crédito",
    status: str = "Confirmado",
    notes: str = "",
    sheet_name: str = "",
    spreadsheet_id: str = "",
) -> str:
    """
    Registra un gasto con análisis avanzado.
    
    Columnas inteligentes:
    1. Fecha - Cuando ocurrió
    2. ID Recibo - Hash único para auditoría
    3. Descripción - Qué se compró
    4. Categoría - Tipo de gasto
    5. Monto - Cantidad
    6. Moneda - USD/EUR/etc
    7. Método Pago - Trazabilidad financiera
    8. Deducible - Importancia fiscal
    9. Estado - Seguimiento del gasto
    10. Hora Exacta - Timestamp para duplicados
    11. Notas - Contexto adicional
    12. Mes/Año - Para reportes automáticos
    """
    
    sid = (spreadsheet_id or DEFAULT_SPREADSHEET_ID).strip()
    title = sheet_name or first_sheet_title(sid)
    
    # Normalizar datos con zona horaria Indochina (ICT)
    ict = pytz.timezone('Asia/Bangkok')  # Zona horaria Indochina
    now = datetime.now(ict)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    month_year = now.strftime("%B %Y")  # Ej: "January 2025"
    amt = (amount or "").replace(",", ".")
    
    # Validar monto
    try:
        amt_float = float(amt)
        if amt_float <= 0:
            return "❌ El monto debe ser mayor a 0"
    except ValueError:
        return f"❌ Monto inválido: {amt}"
    
    # Generar ID único del recibo
    receipt_id = generate_receipt_id(description, amt, date_str + time_str)
    
    # Determinar si es deducible
    is_deductible = calculate_tax_category(amt_float, category)
    
    # Validar status
    try:
        status_val = ExpenseStatus[status.upper().replace(" ", "_")]
    except KeyError:
        status_val = ExpenseStatus.CONFIRMADO
    
    # Validar método de pago
    try:
        payment_val = PaymentMethod[payment_method.upper().replace(" ", "_")]
    except KeyError:
        payment_val = PaymentMethod.OTRO
    
    # Crear fila con todas las columnas inteligentes
    values = [[
        date_str,                          # A: Fecha
        receipt_id,                        # B: ID Recibo (auditoría)
        description,                       # C: Descripción
        category,                          # D: Categoría
        amt,                               # E: Monto
        currency,                          # F: Moneda
        payment_val.value,                 # G: Método Pago (trazabilidad)
        is_deductible,                     # H: Deducible? (fiscal)
        status_val.value,                  # I: Estado (seguimiento)
        time_str,                          # J: Hora Exacta (anti-duplicados)
        notes,                             # K: Notas adicionales
        month_year,                        # L: Mes/Año (reportes)
    ]]
    
    try:
        sheets().spreadsheets().values().append(
            spreadsheetId=sid,
            range=f"{title}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()
        
        return (
            f"✅ GASTO REGISTRADO\n"
            f"📋 Recibo: {receipt_id}\n"
            f"📅 {date_str} {time_str}\n"
            f"💰 {amt} {currency}\n"
            f"📝 {description}\n"
            f"🏷️  {category}\n"
            f"💳 {payment_val.value}\n"
            f"📊 Deducible: {is_deductible}\n"
            f"📍 Estado: {status_val.value}"
        )
    
    except Exception as e:
        return f"❌ Error al registrar: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")