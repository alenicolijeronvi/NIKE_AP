import pandas as pd
from datetime import datetime
import os

# --- IMPORTAMOS LÓGICA CLÁSICA (CALZADO) ---
# Se asume que estos archivos originales siguen existiendo con sus nombres antiguos
import scraper_utils
import fairplay_scraper
import marathon_scraper
import taf_scraper

# --- IMPORTAMOS LÓGICA NUEVA (ROPA) ---
# Usamos try/except por seguridad, pero con los nombres corregidos
try:
    import utils_ropa
    import fairplay_ropa
    import marathon_ropa
    import taf_ropa
except ImportError as e:
    print(f"⚠️ ADVERTENCIA: Falló la carga de módulos de ropa: {e}")

def get_user_inputs():
    print("\n" + "="*50)
    print("   NIKE BOLIVIA - SCRAPER MULTITIENDA v4.5 (SIMPLIFICADO)")
    print("="*50)

    # 1. GÉNERO
    print("\n[1] SELECCIONE GÉNERO:")
    print("1. Hombre")
    print("2. Mujer")
    g_opt = input(">> Opción (1-2): ").strip()
    gender = 'mujer' if g_opt == '2' else 'hombre'

    # 2. TIPO DE EXTRACCIÓN (SIMPLIFICADO)
    print(f"\n[2] ¿QUÉ DESEA BUSCAR PARA {gender.upper()}?:")
    print("1. CALZADO (Clasificado por Deporte: Correr, Futbol, etc.)")
    print("2. TODA LA ROPA (Barrido completo de indumentaria)")
    
    m_opt = input(">> Opción (1-2): ").strip()
    
    if m_opt == '2':
        # Retornamos flag especial para ropa general
        return gender, 'ropa_general', 'indumentaria-total'
    
    # Si es calzado, pedimos deporte
    prod_type = 'calzado'
    print(f"\n[3] DEPORTE ({gender.upper()} - CALZADO):")
    print("1. Correr")
    print("2. Futbol")
    print("3. Entrenamiento")
    print("4. Tenis")
    print("5. Basquet")
    print("6. Lifestyle (Urbano)")
    
    s_opt = input(">> Opción (1-6): ").strip()
    sport_map = {
        '1': 'correr', '2': 'futbol', '3': 'entrenamiento', 
        '4': 'tenis', '5': 'basquet', '6': 'lifestyle'
    }
    category_key = sport_map.get(s_opt, 'correr')

    return gender, prod_type, category_key

def main():
    gender, prod_type, category_key = get_user_inputs()
    start_time = datetime.now()
    
    # Listas para almacenar datos
    data_fp = []
    data_yuth = []
    data_taf = []
    data_ms = []

    # URLs iniciales
    url_fp, url_ms, url_yuth, url_taf = None, None, None, None

    # --- LÓGICA DE RAMIFICACIÓN ---
    if prod_type == 'ropa_general':
        # >>> MODO ROPA GENERAL (Usa archivos *_ropa.py) <<<
        print(f"\n🚀 MODO ACTIVADO: BARRIDO TOTAL DE ROPA ({gender.upper()})")
        print("⚠️  Usando motores dedicados de ropa")
        print("-" * 50)
        
        # Generar URLs usando utils_ropa
        url_fp, url_ms, url_yuth, url_taf = utils_ropa.generate_urls(gender)

        if url_fp: data_fp = fairplay_ropa.scrape(url_fp, "Ropa", "Indumentaria", gender, store_name='Fairplay')
        if url_yuth: data_yuth = fairplay_ropa.scrape(url_yuth, "Ropa", "Indumentaria", gender, store_name='Yuth')
        if url_taf: data_taf = taf_ropa.scrape(url_taf, "Ropa", "Indumentaria", gender)
        if url_ms: data_ms = marathon_ropa.scrape(url_ms, "Ropa", "Indumentaria", gender)

    else:
        # >>> MODO CALZADO (Usa archivos originales *_scraper.py) <<<
        print(f"\n🚀 MODO ACTIVADO: EXTRACCIÓN CALZADO ({category_key.upper()})")
        print("ℹ️  Usando motores de calzado")
        print("-" * 50)
        
        # Generar URLs usando scraper_utils (antiguo)
        url_fp, url_ms, url_yuth, url_taf = scraper_utils.generate_urls(category_key, gender, prod_type)
        
        if url_fp: data_fp = fairplay_scraper.scrape(url_fp, category_key, category_key, gender, store_name='Fairplay')
        if url_yuth: data_yuth = fairplay_scraper.scrape(url_yuth, category_key, category_key, gender, store_name='Yuth')
        if url_taf: data_taf = taf_scraper.scrape(url_taf, category_key, category_key, gender)
        if url_ms: data_ms = marathon_scraper.scrape(url_ms, category_key, category_key, gender)

    # --- CONSOLIDACIÓN ---
    all_data = data_fp + data_yuth + data_taf + data_ms
    
    if all_data:
        df = pd.DataFrame(all_data)
        
        cols = [
            'Tienda', 'Genero', 'Deporte', 'Producto', 'Marca', 'Modelo', 
            'SKU', 'Precio Regular (Bs)', 'Descuento (%)', 'Precio Final (Bs)', 'Link'
        ]
        
        for c in cols:
            if c not in df.columns: df[c] = ""
        df = df[cols]

        print("\n--- LIMPIEZA Y AUDITORÍA ---")
        df['SKU'] = df['SKU'].astype(str).str.strip()
        df_clean = df.drop_duplicates(subset=['Tienda', 'SKU'], keep='first')
        
        today = datetime.now().strftime('%Y-%m-%d_%H-%M')
        # Nombre del archivo dinámico
        if prod_type == 'ropa_general':
             filename = f"DB_ROPA_GENERAL_{gender}_{today}.csv"
        else:
             filename = f"DB_{gender}_{prod_type}_{category_key}_{today}.csv"
             
        abs_path = os.path.abspath(filename)
        
        try:
            df_clean.to_csv(filename, index=False, encoding='utf-8-sig')
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            print(f"\n{'='*30}")
            print(f"✅ REPORTE GENERADO CON ÉXITO")
            print(f"{'='*30}")
            print(f"📁 Archivo: {abs_path}")
            print(f"⏱️ Duración: {duration}")
            print(f"📊 Resumen:")
            print(f"   - Fairplay: {len(df_clean[df_clean['Tienda'] == 'Fairplay'])}")
            if url_yuth: print(f"   - Yuth:     {len(df_clean[df_clean['Tienda'] == 'Yuth'])}")
            if url_taf:  print(f"   - TAF:      {len(df_clean[df_clean['Tienda'] == 'TAF'])}")
            print(f"   - Marathon: {len(df_clean[df_clean['Tienda'] == 'Marathon'])}")
            print(f"   - Total:    {len(df_clean)}")
        except Exception as e:
            print(f"\n❌ Error al guardar archivo: {e}")
        
    else:
        print("\n❌ No se encontraron datos en ninguna tienda.")

if __name__ == "__main__":
    main()