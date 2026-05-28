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

# --- 2. VALIDACIÓN DE PRODUCTO ---
def is_valid_product(product_name, target_gender):
    name_upper = product_name.upper()
    target_upper = target_gender.upper()
    
    forbidden = ['NIÑO', 'NIÑA', 'INFANT', 'BEBE', 'KIDS', 'JUNIOR', ' GS', ' PS', ' TD']
    if any(x in name_upper for x in forbidden): return False
    
    if target_upper == 'HOMBRE' and ('MUJER' in name_upper or 'WOMEN' in name_upper or 'DAMA' in name_upper): return False
    if target_upper == 'MUJER' and ('HOMBRE' in name_upper or 'MEN' in name_upper or 'CABALLERO' in name_upper): return False
    
    return True

# --- 3. LIMPIEZA DE PRECIOS ---
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
    if ',' in clean and '.' in clean:
        if clean.find(',') < clean.find('.'): clean = clean.replace(',', '')
        else: clean = clean.replace('.', '').replace(',', '.')
    elif ',' in clean: 
         parts = clean.split(',')
         if len(parts[-1]) == 3: clean = clean.replace(',', '') 
         else: clean = clean.replace(',', '.') 
    elif '.' in clean:
         parts = clean.split('.')
         if len(parts[-1]) == 3: clean = clean.replace('.', '')
    try: return float(clean)
    except: return 0.0

# --- 4. EXTRACCIÓN MARCA/MODELO ---
def split_brand_model(full_name):
    if not full_name: return "Desconocido", "Desconocido"
    full_name = full_name.strip()
    known_brands = ['NIKE', 'ADIDAS', 'PUMA', 'REEBOK', 'UNDER ARMOUR', 'HOKA', 'ASICS', 'NEW BALANCE', 'SALOMON', 'UMBRO', 'TOPPER', 'YUTH', 'JORDAN', 'TAF', 'VANS', 'CONVERSE', 'SKECHERS', 'FILA', 'CHAMPION']
    upper_name = full_name.upper()
    
    found_brand = "Desconocido"
    model = full_name
    
    for kb in known_brands:
        if upper_name.startswith(kb):
            found_brand = kb.title()
            model = full_name[len(kb):].strip()
            break
            
    clean_model = re.sub(r'^[-–\s]+', '', model)
    clean_model = re.sub(r'(?i)^(zapatilla|zapatillas|tenis|botines|zap|polera|camiseta|short|pantalón|jacket|chompa|buzo|calza|legging|top)\s+', '', clean_model)
    
    if found_brand == "Desconocido":
        parts = full_name.split(' ', 1)
        if len(parts) == 2: return parts[0].title(), parts[1]
        return parts[0].title(), ""
        
    return found_brand, clean_model

def generate_urls(gender):
    """
    Devuelve las URLs maestras para buscar TODA la indumentaria
    sin filtros de categoría específica.
    """
    if gender == 'hombre':
        url_fairplay = "https://www.fairplay.com.bo/hombre/indumentaria?order=OrderByReleaseDateDESC"
        url_marathon = "https://www.marathon.store/bo/productos/hombre/ropa/c/HROP"
        url_yuth = "https://www.yuth.com.bo/hombre/indumentaria"
        url_taf = "https://taf.com.bo/categoria/hombre/ropa-hombre/"
    else: # mujer
        url_fairplay = "https://www.fairplay.com.bo/mujer/indumentaria?order=OrderByReleaseDateDESC"
        url_marathon = "https://www.marathon.store/bo/productos/mujer/ropa/c/MROP"
        url_yuth = "https://www.yuth.com.bo/mujer/indumentaria"
        url_taf = "https://taf.com.bo/categoria/mujer/ropa-mujer/"

    return url_fairplay, url_marathon, url_yuth, url_taf