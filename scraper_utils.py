import re
import requests
import cloudscraper
import time
from urllib.parse import urlparse

# --- SESIÓN HTTP OPTIMIZADA ---
session = cloudscraper.create_scraper()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
    'Connection': 'keep-alive'
})

# --- CÓDIGOS DE CATEGORÍA MARATHON ---
MARATHON_CODES = {
    # HOMBRE
    ('hombre', 'calzado', 'correr'): 'HCALCRU',
    ('hombre', 'calzado', 'futbol'): 'HCALCFU',
    ('hombre', 'calzado', 'entrenamiento'): 'HCALCTR',
    ('hombre', 'calzado', 'tenis'): 'HCALCTE', 
    ('hombre', 'calzado', 'basquet'): 'HCALCBA', # Mantenemos Basquet
    ('hombre', 'calzado', 'lifestyle'): 'HCALCED',
    
    # MUJER
    ('mujer', 'calzado', 'correr'): 'MCALCRU',
    ('mujer', 'calzado', 'entrenamiento'): 'MCALCTR',
    ('mujer', 'calzado', 'tenis'): 'MCALCTE',
    ('mujer', 'calzado', 'futbol'): 'MCALCFU',
    ('mujer', 'calzado', 'basquet'): 'MCALCBA', # Mantenemos Basquet
    ('mujer', 'calzado', 'lifestyle'): 'MCALCED',
}

# --- MAPA DE PRENDAS ---
GARMENT_MAP = {
    'hombre': {
        't-shirt-corta': {'fp': 'poleras', 'ms': 'camisetas'}, 
        't-shirt-larga': {'fp': 'poleras', 'ms': 'camisetas'},
        'pantalones':    {'fp': 'pantalones', 'ms': 'pantalones'},
        'shorts':        {'fp': 'shorts', 'ms': 'shorts'},
        'chaquetas':     {'fp': 'chaquetas', 'ms': 'chompas'},
    },
    'mujer': {
        'shorts':   {'fp': 'shorts', 'ms': 'shorts'},
        'bra':      {'fp': 'top-deportivo', 'ms': 'tops-y-bras'},
        'poleras':  {'fp': 'poleras', 'ms': 'camisetas'},
        'leggings': {'fp': 'calzas', 'ms': 'leggings'},
        'tanks':    {'fp': 'musculosas', 'ms': 'bvd'},
    }
}

def fetch_html(url, add_desktop=False):
    """Realiza una petición HTTP y devuelve el HTML. Agrega retry y timeouts."""
    try:
        req_url = url
        if add_desktop:
            req_url = url + ('&device=DESKTOP' if '?' in url else '?device=DESKTOP')
        response = session.get(req_url, timeout=15)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"    [Error] HTTP Request falló para {url}: {e}")
        return None

def is_valid_product(product_name, target_gender):
    name_upper = product_name.upper()
    target_upper = target_gender.upper()
    
    forbidden = ['NIÑO', 'NIÑA', 'INFANT', 'BEBE', 'KIDS', 'JUNIOR', ' GS', ' PS', ' TD']
    if any(x in name_upper for x in forbidden): return False
    if target_upper == 'HOMBRE' and ('MUJER' in name_upper or 'WOMEN' in name_upper or 'DAMA' in name_upper): return False
    if target_upper == 'MUJER' and ('HOMBRE' in name_upper or 'MEN' in name_upper or 'CABALLERO' in name_upper): return False
    return True

# --- FUNCIONES DE LIMPIEZA DE PRECIOS ---
def format_price_excel(price_float):
    if not price_float: return "0,00"
    return f"{price_float:.2f}".replace('.', ',')

def clean_price_marathon(price_str):
    if not price_str: return 0.0
    clean = str(price_str).lower().replace('bs', '').replace('bolivianos', '').strip()
    clean = clean.replace(',', '') 
    try: return float(clean)
    except: return 0.0

def clean_price_fairplay(price_str):
    if not price_str: return 0.0
    clean = str(price_str).lower().replace('bs', '').replace('bolivianos', '').strip()
    clean = clean.replace('.', '') 
    clean = clean.replace(',', '.') 
    try: return float(clean)
    except: return 0.0

def clean_price_taf(price_str):
    if not price_str: return 0.0
    clean = str(price_str).lower().replace('bs', '').replace('bolivianos', '').strip()
    # TAF: Formato 1.200,50 o 1,200.50
    if ',' in clean and '.' in clean:
        if clean.find(',') < clean.find('.'): 
            clean = clean.replace(',', '')
        else:
            clean = clean.replace('.', '').replace(',', '.')
    elif ',' in clean: 
         parts = clean.split(',')
         if len(parts[-1]) == 3: clean = clean.replace(',', '') 
         else: clean = clean.replace(',', '.') 
    elif '.' in clean:
         parts = clean.split('.')
         if len(parts[-1]) == 3: clean = clean.replace('.', '')
    try: return float(clean)
    except: return 0.0

def split_brand_model(full_name):
    if not full_name: return "Desconocido", "Desconocido"
    full_name = full_name.strip()
    known_brands = ['NIKE', 'ADIDAS', 'PUMA', 'REEBOK', 'UNDER ARMOUR', 'HOKA', 'ASICS', 'NEW BALANCE', 'SALOMON', 'UMBRO', 'TOPPER', 'YUTH', 'JORDAN', 'TAF', 'VANS', 'CONVERSE']
    upper_name = full_name.upper()
    
    found_brand = "Desconocido"
    model = full_name
    
    for kb in known_brands:
        if upper_name.startswith(kb):
            found_brand = kb.title()
            model = full_name[len(kb):].strip()
            break
            
    clean_model = re.sub(r'^[-–\s]+', '', model)
    clean_model = re.sub(r'(?i)^(zapatilla|zapatillas|tenis|botines|zap)\s+', '', clean_model)
    
    if found_brand == "Desconocido":
        parts = full_name.split(' ', 1)
        if len(parts) == 2: return parts[0].title(), parts[1]
        return parts[0].title(), ""
        
    return found_brand, clean_model

def generate_urls(category_key, gender, prod_type):
    url_fairplay = None
    url_marathon = None
    url_yuth = None
    url_taf = None

    if prod_type == 'calzado':
        sport = category_key
        fp_sport = sport
        if sport == 'entrenamiento': fp_sport = 'entrenar'
        if sport == 'basquet': fp_sport = 'basquetbol'
        
        url_fairplay = f"https://www.fairplay.com.bo/{gender}/zapatillas/{fp_sport}?order=OrderByReleaseDateDESC"
        
        if sport == 'lifestyle':
            url_yuth = f"https://www.yuth.com.bo/{gender}/zapatillas/{fp_sport}?order=OrderByReleaseDateDESC"
            
            # --- TAF ZAPATILLAS (URLs MAESTRAS HARDCODED) ---
            if gender == 'hombre':
                url_taf = "https://taf.com.bo/categoria/hombre/zapatillas/"
            else:
                url_taf = "https://taf.com.bo/categoria/mujer/zapatillas-mujer/"

        ms_sport = 'urbano' if sport == 'lifestyle' else sport
        code = MARATHON_CODES.get((gender, 'calzado', sport))
        
        if code:
            url_marathon = f"https://www.marathon.store/bo/productos/{gender}/calzado/{ms_sport}/c/{code}"
        else:
            url_marathon = f"https://www.marathon.store/bo/productos/{gender}/calzado/{ms_sport}"

    elif prod_type == 'ropa':
        garment_key = category_key
        slugs = GARMENT_MAP.get(gender, {}).get(garment_key)
        
        if slugs:
            fp_slug = slugs['fp']
            ms_slug = slugs['ms']
            url_fairplay = f"https://www.fairplay.com.bo/{gender}/ropa/{fp_slug}?order=OrderByReleaseDateDESC"
            url_yuth = f"https://www.yuth.com.bo/{gender}/ropa/{fp_slug}?order=OrderByReleaseDateDESC"
            url_marathon = f"https://www.marathon.store/bo/productos/{gender}/ropa/{ms_slug}"
            
            # --- TAF ROPA (URLs MAESTRAS HARDCODED) ---
            if gender == 'hombre':
                url_taf = "https://taf.com.bo/categoria/hombre/ropa-hombre/"
            else:
                url_taf = "https://taf.com.bo/categoria/mujer/ropa-mujer/"
        else:
            print(f"⚠️ Error de mapeo: {garment_key}")

    return url_fairplay, url_marathon, url_yuth, url_taf