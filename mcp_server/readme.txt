# Google Sheets Expense Tracker MCP Server (v2)

Servidor MCP para gestionar gastos personales en Google Sheets.

## Nuevas Funcionalidades
- **`create_new_spreadsheet`**: Crea un archivo de Google Sheets desde cero y devuelve su ID.
- **`add_expense`**: Añade gastos con validación de moneda y fecha.
- **`list_recent_expenses`**: Visualiza los últimos movimientos.

## Configuración de Google Cloud
1. Habilita **Google Sheets API** y **Google Drive API** en tu consola de Google Cloud.
2. Configura la pantalla de consentimiento OAuth y añade tu correo como "Test User".
3. Descarga las credenciales como `gcp-oauth.keys.json`.

## Primer Inicio
La primera vez que uses una herramienta, el servidor intentará abrir un navegador para el login. 
Si estás en Docker, revisa los logs para ver la URL de autenticación.

## Ejemplo de uso
1. "Crea una nueva hoja de cálculo para mis gastos de viaje."
2. (Copia el ID recibido)
3. "Añade un gasto de 45.00 USD en comida usando el ID [ID_RECIBIDO]."