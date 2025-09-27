import pandas as pd
from datetime import datetime
import json
from nombres_gpt import extract_name_components_and_gender
from loguru import logger


# Código ISO de República Dominicana y USA
PAIS_ID_RD = 214
PAIS_ID_USA = 840

# === EXTERNAL DEFAULTS For Humano===
AGENCY_ID = 1
SALESMAN_ID = 10
PRODUCTO_ID = 1

# Fecha de corte para filtrado (Abril 2025)
FECHA_CORTE = pd.to_datetime("2025-04-01")

def parse_date_safe(date_value, default_date=None):
    """
    Parsea fechas en formato DD/MM/YYYY de manera segura.
    
    Args:
        date_value: Valor de fecha a parsear
        default_date (str): Fecha por defecto en formato YYYY-MM-DD
        
    Returns:
        str: Fecha en formato YYYY-MM-DD
    """
    if pd.isna(date_value):
        return default_date
    
    try:
        # Intenta primero con formato explícito DD/MM/YYYY
        return pd.to_datetime(date_value, format="%d/%m/%Y").strftime("%Y-%m-%d")
    except:
        try:
            # Fallback a formato automático con dayfirst=True
            return pd.to_datetime(date_value, dayfirst=True).strftime("%Y-%m-%d")
        except:
            logger.warning(f"⚠️ Error parseando fecha: {date_value}, usando valor por defecto: {default_date}")
            return default_date

def add_one_year(date_str):
    """
    Añade un año a una fecha manteniendo el mismo día y mes.
    
    Args:
        date_str (str): Fecha en formato YYYY-MM-DD
        
    Returns:
        str: Nueva fecha en formato YYYY-MM-DD
    """
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        new_date = date.replace(year=date.year + 1)
        return new_date.strftime("%Y-%m-%d")
    except:
        return date_str

def cargar_emisiones_desde_excel(excel_path, output_path=None):
    """
    Carga datos de emisiones desde un archivo Excel y los devuelve como diccionario
    de emisiones indexado por número de factura, listos para la cotización.
    
    Args:
        excel_path (str): Ruta al archivo Excel
        output_path (str, optional): Ruta donde guardar el JSON de emisiones
        
    Returns:
        dict: Diccionario de emisiones con estructura API v3.7
    """
    try:
        logger.info(f"📊 Leyendo archivo Excel: {excel_path}")
        df = pd.read_excel(excel_path, header=4)
        df.columns = df.columns.str.strip()
        
        total_rows = len(df)
        logger.info(f"📝 Total de registros encontrados: {total_rows}")

        # Procesar fechas por columnas de manera eficiente
        logger.info("🕒 Procesando fechas...")
        date_columns = ["FEC_NAC", "INICIO VIGENCIA", "FIN VIGENCIA", "FECHA DE EMISION"]
        for col in date_columns:
            df[col] = df[col].apply(lambda x: parse_date_safe(x, "1990-01-01"))

        # Filtrar registros posteriores a abril 2025
        logger.info("🔍 Filtrando registros posteriores a abril 2025...")
        df['fecha_inicio_dt'] = pd.to_datetime(df['INICIO VIGENCIA'])
        df_filtered = df[df['fecha_inicio_dt'] >= FECHA_CORTE].copy()
        df_filtered = df_filtered.drop('fecha_inicio_dt', axis=1)
        
        filtered_rows = len(df_filtered)
        logger.info(f"📊 Registros después del filtrado: {filtered_rows} de {total_rows}")

        emisiones = {}
        errores = []
        procesados = 0

        for factura, grupo in df_filtered.groupby("FACTURA"):
            try:
                insured = []
                for _, row in grupo.iterrows():
                    try:
                        # Extraer y validar datos del asegurado
                        nombre_completo = str(row.get("NOMBRE AFILIADO", "")).strip()
                        if not nombre_completo:
                            raise ValueError("Nombre del afiliado está vacío")

                        # Generar pasaporte único
                        asegurado = str(row.get("ASEGURADO", "")).strip()
                        dep = str(row.get("DEP.", "")).strip()
                        pasaporte = f"{asegurado}-{dep}" if asegurado and dep else "SIN-PASAPORTE"

                        # Procesar nombre y género
                        first, last1, last2, middle, gender = extract_name_components_and_gender(nombre_completo)
                        firstname = first.upper() if first else nombre_completo.split()[0].upper()
                        lastname = f"{last1} {last2}".strip().upper() if last1 else " ".join(nombre_completo.split()[1:]).upper()
                        gender_value = gender[0].upper() if gender else "M"

                        insured.append({
                            "identity": "",
                            "passport": pasaporte,
                            "firstname": firstname or ".",
                            "lastname": lastname or ".",
                            "birthdate": row["FEC_NAC"],
                            "gender": gender_value
                        })

                    except Exception as e:
                        logger.warning(f"⚠️ Error procesando asegurado en factura {factura}: {str(e)}")
                        continue

                if not insured:
                    raise ValueError("No se pudieron procesar asegurados para esta factura")

                # Procesar fechas y añadir un año
                first = grupo.iloc[0]
                fecha_inicio = add_one_year(first["INICIO VIGENCIA"])
                fecha_fin = add_one_year(first["FIN VIGENCIA"])
                fecha_emision = first["FECHA DE EMISION"]

                # Crear dirección por defecto
                addresses = [{
                    "line1": ".",
                    "line2": "",
                    "city": ".",
                    "state": ".",
                    "country_id": PAIS_ID_RD,
                    "zip": "00000",
                    "phone": ["."],
                    "email": ["."],
                    "kind": "Por defecto"
                }]

                # Construir emisión
                emisiones[factura] = {
                    "metadata": {
                        "fecha_emision": fecha_emision,
                        "total_asegurados": len(insured),
                        "plan": str(first.get("DESCRIPCION PLAN", "")).strip() or "PLAN NO ESPECIFICADO",
                        "estado": "pendiente",
                        "estado_facturacion": str(first.get("ESTADO FACTURACION", "")).strip() or "NO ESPECIFICADO"
                    },
                    "emision": {
                        "agency_id": AGENCY_ID,
                        "discount": 0.00,
                        "salesman_id": SALESMAN_ID,
                        "products": [{"id": PRODUCTO_ID}],
                        "destiny_id": PAIS_ID_USA,
                        "destination_id": PAIS_ID_USA,
                        "from": fecha_inicio,
                        "to": fecha_fin,
                        "terms": "",
                        "insured": insured,
                        "addresses": addresses
                    }
                }
                procesados += 1
                if procesados % 10 == 0:
                    logger.info(f"✓ Procesados {procesados}/{filtered_rows} registros...")

            except Exception as e:
                errores.append(f"Error en factura {factura}: {str(e)}")
                logger.error(f"❌ Error procesando factura {factura}: {str(e)}")
                continue

        # Guardar resultados
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(emisiones, f, ensure_ascii=False, indent=2)
            logger.success(f"✅ {len(emisiones)} emisiones generadas y guardadas en '{output_path}'")

        # Mostrar resumen
        logger.info("\n📊 Resumen del procesamiento:")
        logger.info(f"Total de registros originales: {total_rows}")
        logger.info(f"Registros posteriores a abril 2025: {filtered_rows}")
        logger.info(f"Emisiones generadas: {len(emisiones)}")
        logger.info(f"Errores encontrados: {len(errores)}")

        # Si hay errores, guardarlos en un archivo
        if errores and output_path:
            error_path = output_path.replace('.json', '_errores.txt')
            with open(error_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(errores))
            logger.warning(f"⚠️ Lista de errores guardada en: {error_path}")

        return emisiones

    except Exception as e:
        logger.error(f"Error al cargar emisiones desde Excel: {str(e)}")
        raise

if __name__ == "__main__":
    EXCEL_PATH = "/app/viajeros_pipeline/Exceles/Rep_Afiliados_Seguro_Viajero 16 06 2025 AL 02 07 2025.xlsx"
    OUTPUT_PATH = "/app/viajeros_pipeline/emisiones_generadas.json"
    cargar_emisiones_desde_excel(EXCEL_PATH, OUTPUT_PATH) 
