import pandas as pd
from datetime import datetime
import json
from loguru import logger
import re
import unicodedata


# Código ISO de República Dominicana y USA
PAIS_ID_RD = 214
PAIS_ID_USA = 840

# === EXTERNAL DEFAULTS For Humano===
AGENCY_ID = 1
SALESMAN_ID = 10
PRODUCTO_ID = 1

# Fecha de corte para filtrado (Abril 2025)
FECHA_CORTE = pd.to_datetime("2025-04-01")

# Nombres de columnas para fechas
COL_FECHA_INICIO = "FEC_INI"
COL_FECHA_FIN = "FEC_FIN"
COL_FECHA_NAC = "FEC_NAC"
COL_FECHA_EMISION = "FECHA_EMISION"

# Otros nombres de columnas
COL_MODALIDAD = "MODALIDAD_TARIFA"

def is_valid_dominican_cedula(cedula):
    """
    Valida si una cédula dominicana es válida.
    
    Args:
        cedula (str): Número de cédula a validar
        
    Returns:
        bool: True si es una cédula válida, False en caso contrario
    """
    try:
        # Si es None o vacío, retornar False
        if pd.isna(cedula) or not str(cedula).strip():
            return False

        # Eliminar espacios y guiones
        cedula = str(cedula).strip().replace(' ', '').replace('-', '')
        
        # Eliminar cualquier otro caracter no numérico
        cedula = re.sub(r'[^0-9]', '', cedula)
        
        # Verificar longitud
        if len(cedula) != 11:
            logger.debug(f"Cédula {cedula} inválida: longitud incorrecta ({len(cedula)} dígitos)")
            return False
            
        # Verificar que solo contiene números
        if not cedula.isdigit():
            logger.debug(f"Cédula {cedula} inválida: contiene caracteres no numéricos")
            return False
            
        # Verificar que no son todos números iguales
        if len(set(cedula)) == 1:
            logger.debug(f"Cédula {cedula} inválida: todos los dígitos son iguales")
            return False
            
        # Verificar que comienza con dígitos válidos para cédula dominicana
        valid_starts = ['001', '002', '003', '004', '402']
        if not any(cedula.startswith(start) for start in valid_starts):
            logger.debug(f"Cédula {cedula} inválida: prefijo no válido")
            return False
            
        # Verificar que no es una cédula obviamente inválida
        invalid_numbers = [
            '00000000000', '11111111111', '22222222222', 
            '33333333333', '44444444444', '55555555555',
            '66666666666', '77777777777', '88888888888', 
            '99999999999'
        ]
        if cedula in invalid_numbers:
            logger.debug(f"Cédula {cedula} inválida: número obviamente inválido")
            return False

        # Algoritmo de validación de cédula dominicana
        weights = [1, 2, 1, 2, 1, 2, 1, 2, 1, 2]
        total = 0
        
        # Calcular suma ponderada
        for i in range(10):
            digit = int(cedula[i])
            weighted = digit * weights[i]
            # Si el resultado es de dos dígitos, sumar los dígitos
            total += sum(int(d) for d in str(weighted))
            
        # Calcular dígito verificador esperado
        check_digit = (10 - (total % 10)) % 10
        
        # Comparar con el último dígito de la cédula
        is_valid = check_digit == int(cedula[-1])
        if not is_valid:
            logger.debug(f"Cédula {cedula} inválida: dígito verificador incorrecto")
        
        return is_valid
        
    except Exception as e:
        logger.warning(f"Error validando cédula {cedula}: {str(e)}")
        return False

def parse_date_safe(date_value, default_date=None):
    """
    Parsea fechas en formato DD/MM/YYYY o timestamps en formato YYYY-MM-DD HH:MM:SS de manera segura.
    
    Args:
        date_value: Valor de fecha a parsear
        default_date (str): Fecha por defecto en formato YYYY-MM-DD
        
    Returns:
        str: Fecha en formato YYYY-MM-DD
    """
    if pd.isna(date_value):
        return default_date
    
    try:
        # Si es un timestamp de pandas, convertir directamente
        if isinstance(date_value, pd.Timestamp):
            return date_value.strftime("%Y-%m-%d")
            
        # Si es string, intentar diferentes formatos
        if isinstance(date_value, str):
            # Primero intentar con formato DD/MM/YYYY
            try:
                return pd.to_datetime(date_value, format="%d/%m/%Y").strftime("%Y-%m-%d")
            except:
                # Si falla, intentar con formato automático
                return pd.to_datetime(date_value, dayfirst=True).strftime("%Y-%m-%d")
        
        # Para otros tipos (datetime, etc)
        return pd.to_datetime(date_value).strftime("%Y-%m-%d")
        
    except Exception as e:
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

def clean_name(text):
    """
    Limpia el texto de caracteres especiales y símbolos manteniendo solo letras, espacios y algunos caracteres permitidos.
    
    Args:
        text (str): Texto a limpiar
        
    Returns:
        str: Texto limpio
    """
    if not isinstance(text, str):
        return ""
        
    # Normalizar caracteres unicode (convierte ñ, tildes, etc. a sus equivalentes básicos)
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ASCII', 'ignore').decode('ASCII')
    
    # Convertir a mayúsculas y eliminar caracteres no deseados
    text = text.upper()
    
    # Eliminar caracteres especiales pero mantener espacios y letras
    text = re.sub(r'[^A-Z\s]', '', text)
    
    # Eliminar espacios múltiples
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def process_name_field(first_part, second_part):
    """
    Procesa y combina partes de nombre/apellido asegurando que no excedan 30 caracteres.
    Limpia caracteres especiales y símbolos.
    
    Args:
        first_part (str): Primera parte del nombre/apellido
        second_part (str): Segunda parte del nombre/apellido
        
    Returns:
        str: Combinación de las partes que no excede 30 caracteres
    """
    first = clean_name(str(first_part) if not pd.isna(first_part) else "")
    second = clean_name(str(second_part) if not pd.isna(second_part) else "")
    
    combined = f"{first} {second}".strip()
    # Tomar los primeros 30 caracteres de la combinación
    return combined[:30]

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
        df = pd.read_excel(excel_path)
        df.columns = df.columns.str.strip()
        
        total_rows = len(df)
        logger.info(f"📝 Total de registros encontrados: {total_rows}")

        # Procesar fechas por columnas de manera eficiente
        logger.info("🕒 Procesando fechas...")
        date_columns = [COL_FECHA_NAC, COL_FECHA_INICIO, COL_FECHA_FIN, COL_FECHA_EMISION]
        for col in date_columns:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: parse_date_safe(x, "1990-01-01"))

        # Filtrar registros posteriores a abril 2025
        logger.info("🔍 Filtrando registros posteriores a abril 2025...")
        df['fecha_inicio_dt'] = pd.to_datetime(df[COL_FECHA_INICIO])
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
                        # Procesar nombres y apellidos
                        firstname = process_name_field(row.get("PRI_NOM", ""), row.get("SEG_NOM", ""))
                        lastname = process_name_field(row.get("PRI_APE", ""), row.get("SEG_APE", ""))
                        
                        if not firstname or not lastname:
                            raise ValueError("Nombre o apellido está vacío")

                        # Validar y obtener documento de identidad
                        documento = str(row.get("DOCUMENTO_IDENTIDAD", "")).strip()
                        # Solo usar el documento si es una cédula dominicana válida
                        identity = documento if is_valid_dominican_cedula(documento) else ""
                        
                        # Obtener pasaporte (siempre usar ASEGURADO como pasaporte)
                        passport = str(row.get("ASEGURADO", "")).strip()
                        
                        # Obtener género
                        gender = str(row.get("SEXO", "M")).strip().upper()
                        if gender not in ["M", "F"]:
                            gender = "M"  # Valor por defecto si no es válido

                        insured.append({
                            "identity": identity,
                            "passport": passport,
                            "firstname": firstname.upper(),
                            "lastname": lastname.upper(),
                            "birthdate": row[COL_FECHA_NAC],
                            "gender": gender
                        })

                    except Exception as e:
                        logger.warning(f"⚠️ Error procesando asegurado en factura {factura}: {str(e)}")
                        continue

                if not insured:
                    raise ValueError("No se pudieron procesar asegurados para esta factura")

                # Obtener fechas del primer registro del grupo
                first = grupo.iloc[0]
                fecha_inicio = first[COL_FECHA_INICIO]
                fecha_fin = first[COL_FECHA_FIN]
                fecha_emision = first[COL_FECHA_EMISION]

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
                        "plan": str(first.get(COL_MODALIDAD, "")).strip() or "PLAN NO ESPECIFICADO",
                        "estado": "pendiente",
                        "estado_facturacion": str(first.get("ESTADO_FACTURACION", "")).strip() or "NO ESPECIFICADO"
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
    EXCEL_PATH = "/app/si_pipeline/Comparador_Humano/exceles/Asegurados_SI.xlsx"
    OUTPUT_PATH = "/app/si_pipeline/emisiones_generadas.json"
    cargar_emisiones_desde_excel(EXCEL_PATH, OUTPUT_PATH) 
