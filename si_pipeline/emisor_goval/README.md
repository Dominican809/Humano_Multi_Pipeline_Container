# 🧾 Automatizador de Emisión de Seguros - Goval API

Este proyecto permite **emitir pólizas de seguro de viaje** automáticamente utilizando la [API Goval-Web v3.7](./API%20Goval-Web%20v3.7-1.pdf). El sistema sigue el flujo oficial de emisión, tal como se describe en el documento (páginas 104–114), implementado en Python de forma modular y clara.

---

## 📚 Requisitos
- Python 3.9 o superior
- `requests` (para llamadas a la API)

Instalar dependencias:
```bash
pip install requests
```

---

## 🗂️ Estructura del Proyecto

```
emisor_goval/
├── main.py                 # Entrada principal: emite pólizas en lote
├── config.py               # Credenciales y parámetros generales
├── api/
│   ├── auth.py             # Login y token JWT
│   ├── cotizacion.py       # Cotiza y valida los datos del seguro
│   └── pago.py             # Aplica pago con línea de crédito
└── README.md               # Documentación del proyecto
```

---

## 🧭 Flujo de Emisión (según la documentación GAPI)

GAPI requiere un proceso transaccional en **3 pasos**, descrito en la página **104** del documento.

### 1. 🔐 Login y token JWT
- Endpoint: `POST /api/security/login`
- Devuelve un token con 5 minutos de validez.
- Obligatorio para toda solicitud posterior.

📄 Ver página 13–14 del documento `API Goval-Web v3.7-1.pdf`

---

### 2. 📥 Cotización
- Endpoint: `POST /api/issue/retail/new`
- Estructura completa del cuerpo:
  - `agency_id`, `salesman_id`, `products`, `from`, `to`, `insured`, `addresses`
- Devuelve: `id` de la cotización (requerido para el siguiente paso)

📄 Ver página 112–113 de la documentación

✔️ Esto valida que la persona pueda ser asegurada, y calcula el precio exacto.

---

### 3. 💳 Aplicación de Pago / Emisión
- Endpoint: `POST /api/issue/retail/apply/{id}/credit`
- Usa el `id` de cotización y lo convierte en un certificado emitido
- Requiere permisos del productor para usar línea de crédito

📄 Ver página 122 del documento

---

## 🧪 Ejecución del script

Edita `main.py` y personaliza la lista de personas aseguradas. Luego corre:
```bash
python main.py
```

El sistema:
- Se loguea y obtiene el token.
- Cotiza para cada persona.
- Emite la póliza usando crédito.
- Muestra resultados por consola.

---

## ✅ ¿Cómo adaptar a producción?
- Cambiar `API_BASE` en `config.py` a:
  ```python
  API_BASE = "https://govalapi.govalseguros.com"
  ```
- Usar credenciales reales de producción.

---

## 📌 Notas adicionales
- El token puede caducar en medio de una ejecución larga. Aquí se genera una sola vez por simplicidad.
- Se recomienda agregar manejo automático de reintento con renovación de token si se automatiza con cientos de registros.
- El campo `pais_id` debe ser el código ISO numérico (ej. 214 para República Dominicana).

---

## 📄 Referencias del documento API
- Página 13: Autenticación y token
- Página 104: Flujo transaccional
- Página 112: Cotización (`/issue/retail/new`)
- Página 122: Aplicar pago (`/apply/{id}/credit`)

---

¿Dudas o deseas adaptar este proyecto a lectura desde Excel o integración web? Contáctame o continúa desarrollando desde esta base modular y segura. ✅ 