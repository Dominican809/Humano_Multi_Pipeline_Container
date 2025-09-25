import openai
import re
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
openai.api_key = api_key

# In-memory cache to avoid repeated API calls for the same name
_name_cache = {}

def truncate_component(component, max_length=30):
    """Truncate a name component to the specified maximum length."""
    return component[:max_length] if component else ""

def smart_fallback(name, gender="M"):
    """
    Fallback that maximizes information preservation:
    - Uses first 30 chars for first_name
    - Uses next 30 chars for paternal_last_name
    - Ensures we don't cut words in the middle when possible
    """
    name_clean = " ".join(name.strip().split())  # Normalize spaces
    
    # If name is 60 chars or less, try to split at last space in first 30 chars
    if len(name_clean) <= 60:
        # Try to find a natural word boundary in the first 30 chars
        space_pos = name_clean[:30].rfind(' ')
        if space_pos > 0:
            first = name_clean[:space_pos]
            last = name_clean[space_pos + 1:]
        else:
            # No space found, just split at 30
            first = name_clean[:30]
            last = name_clean[30:]
    else:
        # For names > 60 chars, use maximum allowed space
        # Try to find a natural word boundary in the first 30 chars
        space_pos = name_clean[:30].rfind(' ')
        if space_pos > 0:
            first = name_clean[:space_pos]
            remaining = name_clean[space_pos + 1:]
            # Take up to 30 chars from remaining for last name
            last = remaining[:30]
        else:
            # No natural break found, use hard limits
            first = name_clean[:30]
            last = name_clean[30:60]
    
    return [first.strip(), last.strip(), "", "", gender]

def extract_name_components_and_gender(name):
    if name in _name_cache:
        return _name_cache[name]

    # === Prompt ===
    prompt = (
        f"You are to strictly parse the following full name: '{name}'.\n\n"

        f"LANGUAGE AND CULTURE:\n"
        f"- Names will most likely come from Latin America (e.g., Dominican Republic, Mexico, Colombia, Peru), but may vary in origin.\n"
        f"- By default, you must apply Spanish-language naming conventions, unless the structure clearly reflects a different culture.\n"
        f"- Spanish naming conventions include the use of one or more given names, and one or two surnames (paternal and maternal), possibly including particles like 'de', 'del', or 'de la'.\n"
        f"- Do NOT apply English or non-Hispanic naming rules unless it is unmistakably appropriate.\n\n"

        f"CONTEXT:\n"
        f"- Names may include compound first names (e.g., 'José Luis') and compound surnames (e.g., 'De la Cruz', 'Del Río').\n"
        f"- Spanish prepositions and particles like 'de', 'del', 'de la', 'los', etc. must be preserved and attached to surnames as relevant.\n"
        f"- Accents and special characters (á, é, í, ó, ú, ñ, ü, etc.) must be preserved **exactly** as written.\n"
        f"- Preserve the original capitalization of all name components.\n\n"

        f"ORDER AND INTEGRITY:\n"
        f"- You must NEVER omit, drop, or ignore any word from the input name. Every token must appear in the output.\n"
        f"- NEVER invent or reorder any token from the input.\n"
        f"- If you concatenate the first four fields in order (excluding gender), they must exactly reconstruct the input name, preserving both word order and spacing.\n"
        f"- The total number of words in the output (excluding the gender field) must match the number of words in the input.\n\n"

        f"FORMAT:\n"
        f"- Your response must be a valid Python-style list.\n"
        f"- The list must contain exactly 5 elements, in this strict order:\n"
        f"  ['first_name(s)', 'paternal_last_name', 'maternal_last_name', 'middle_name(s)', 'gender']\n"
        f"- Each element must be a **string enclosed in single or double quotes** (e.g., 'José' or \"José\").\n"
        f"- The gender field must be either 'M' or 'F' (quoted).\n"
        f"- All elements must be strings, even if empty. For example: ['', '', '', '', 'M']\n"
        f"- The list must start with `[` and end with `]` — no line breaks, no explanation, no additional formatting.\n\n"

        f"SPECIAL INSTRUCTIONS:\n"
        f"- You must NEVER omit any word from the input.\n"
        f"- If uncertain how to classify a token, include it rather than excluding it.\n"
        f"- Middle name(s) may be left empty, but never include last name components in that field.\n"
        f"- Compound surnames (e.g., 'García Márquez', 'de los Santos') must be kept intact in a single surname field.\n"
        f"- If the name contains initials (e.g., 'J.'), include them as part of the relevant name field.\n"
        f"- If you are unsure how to split the name, apply this fallback rule:\n"
        f"   • Assign the **first token** to 'first_name(s)'\n"
        f"   • Assign **all remaining tokens** to 'paternal_last_name'\n"
        f"   • Leave both 'maternal_last_name' and 'middle_name(s)' as empty strings\n\n"

        f"EXAMPLES (follow this format strictly):\n"
        f"Input: 'María Fernanda González Pérez'\n"
        f"→ Output: ['María Fernanda', 'González', 'Pérez', '', 'F']\n\n"
        f"Input: 'Luis Alberto del Río'\n"
        f"→ Output: ['Luis', 'del Río', '', 'Alberto', 'M']\n\n"
        f"Input: 'José Marmolejo Roa'\n"
        f"→ Output: ['José', 'Marmolejo', 'Roa', '', 'M']\n\n"
        f"Input: 'Ana de los Santos'\n"
        f"→ Output: ['Ana', 'de los Santos', '', '', 'F']\n\n"
        f"Input: 'Pedro'\n"
        f"→ Output: ['Pedro', '', '', '', 'M']\n\n"

        f"Now return the result ONLY as a Python list:"
    )

    # === System Message ===
    system_message = {
        "role": "system",
        "content": (
            "You are a strict, detail-oriented assistant specialized in parsing full names into structured data.\n\n"
            "Most names you will process come from Latin America (e.g., Dominican Republic, Mexico, Colombia), but names may also come from other regions. "
            "By default, you must apply Spanish-language naming conventions, unless the structure clearly reflects a different culture.\n\n"
            "Your task is to split full names into exactly five components:\n"
            "['first_name(s)', 'paternal_last_name', 'maternal_last_name', 'middle_name(s)', 'gender']\n\n"
            "You must NEVER omit, ignore, invent, or reorder any word from the original input. "
            "When we say 'preserve token order', we mean that the exact sequence of words in the input name — as written — must be preserved in the output fields. "
            "If you concatenate the first four fields (excluding gender), the full name must exactly match the original input name in order and spacing.\n\n"
            "Gender must be returned strictly as 'M' or 'F'. If uncertain, default to 'M'.\n"
            "Return ONLY a clean Python-style list. No explanations, no extra text, no formatting artifacts.\n\n"
            "If unsure how to split the name, assign the first token to 'first_name(s)', the rest to 'paternal_last_name', and leave the remaining fields empty."
        )
    }

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                system_message,
                {"role": "user", "content": prompt},
            ]
        )

        result = response.choices[0].message.content
        list_match = re.search(r'\[.*?\]', result)
        if list_match:
            list_str = list_match.group(0)
            parsed = eval(list_str)

            # === Inline validation ===
            if (
                isinstance(parsed, list) and
                len(parsed) == 5 and
                parsed[-1] in ("M", "F") and
                all(isinstance(x, str) for x in parsed)
            ):
                # Truncate each component to 30 characters
                first_name = truncate_component(parsed[0])
                paternal = truncate_component(parsed[1])
                maternal = truncate_component(parsed[2])
                middle = truncate_component(parsed[3])
                gender = parsed[4]

                # Validate the reconstruction
                input_tokens = " ".join(name.strip().split())
                output_tokens = " ".join(" ".join([first_name, middle, paternal, maternal]).strip().split())
                
                if len(output_tokens.replace(" ", "")) <= len(input_tokens.replace(" ", "")):
                    result = [first_name, paternal, maternal, middle, gender]
                    _name_cache[name] = result
                    return result
                
        # If GPT parsing or validation fails, use smart fallback
        fallback = smart_fallback(name)
        _name_cache[name] = fallback
        return fallback

    except Exception as e:
        # Total fallback if GPT fails entirely
        return smart_fallback(name)
