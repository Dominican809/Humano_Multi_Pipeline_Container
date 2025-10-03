import pandas as pd
import json
from datetime import datetime
import calendar
import re
import unicodedata

PAIS_ID_RD = 214
PAIS_ID_USA = 840

AGENCY_ID = 1
SALESMAN_ID = 10
PRODUCTO_ID = 2

def clean_name(text):
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    text = text.upper()
    text = re.sub(r'[^A-Z\s]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def process_name(first, second):
    first_clean = clean_name(first)
    second_clean = clean_name(second)
    return (first_clean + ' ' + second_clean).strip()[:30]

def parse_date_safe(date_value, default="1990-01-01"):
    try:
        return pd.to_datetime(date_value).strftime("%Y-%m-%d")
    except:
        return default

def create_single_emission(excel_path, output_path):
    df = pd.read_excel(excel_path)
    df.columns = df.columns.str.strip()

    insured_list = []
    for _, row in df.iterrows():
        firstname = process_name(row.get("PRI_NOM", ""), row.get("SEG_NOM", ""))
        lastname = process_name(row.get("PRI_APE", ""), row.get("SEG_APE", ""))
        passport = str(row.get("CODIGO_INFOPLAN", "")).strip()  # Now using CODIGO_INFOPLAN
        gender = str(row.get("SEXO", "M")).strip().upper()
        gender = gender if gender in ["M", "F"] else "M"
        birthdate = parse_date_safe(row.get("FEC_NAC"))

        insured_list.append({
            "identity": "",
            "passport": passport,
            "firstname": firstname,
            "lastname": lastname,
            "birthdate": birthdate,
            "gender": gender
        })

    first_row = df.iloc[0]
    
    # Calculate dynamic date interval for the entire current month
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    
    # First day of current month
    from_date = f"{current_year}-{current_month:02d}-01"
    
    # Last day of current month
    last_day = calendar.monthrange(current_year, current_month)[1]
    to_date = f"{current_year}-{current_month:02d}-{last_day:02d}"

    # Generate a temporary policy number (you might want to adjust this logic)
    policy_number = datetime.now().strftime("%Y%m%d%H%M")

    emission_data = {
        policy_number: {  # Wrap the emission data with a policy number
            "metadata": {
                "fecha_emision": datetime.now().strftime("%Y-%m-%d"),  # Add fecha_emision
                "total_asegurados": len(insured_list),
                "plan": str(first_row.get("MODALIDAD_TARIFA", "VIAJERO MEDICO INTERNACIONAL (SMI)")),
                "estado": "pendiente",
                "estado_facturacion": "NO ESPECIFICADO"  # Add estado_facturacion
            },
            "emision": {
                "agency_id": AGENCY_ID,
                "discount": 0.00,
                "salesman_id": SALESMAN_ID,
                "products": [{"id": PRODUCTO_ID}],
                "destiny_id": PAIS_ID_USA,
                "destination_id": PAIS_ID_USA,
                "from": from_date,
                "to": to_date,
                "terms": "",
                "insured": insured_list,
                "addresses": [{
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
            }
        }
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(emission_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Emission with {len(insured_list)} passengers saved to {output_path}")

"""
if __name__ == "__main__":
    # Example Usage
    create_single_emission("/app/si_pipeline/Comparador_Humano/exceles/comparison_result.xlsx", "/app/si_pipeline/emision_unica.json")
"""