import streamlit as st
import pandas as pd
from datetime import datetime
import time

# --- IMPORT STANDARD SCRAPERS (FOOTWEAR) ---
import scraper_utils as utils
import fairplay_scraper
import marathon_scraper
import taf_scraper

# --- IMPORT CLOTHING SCRAPERS (ROPA) ---
try:
    import utils_ropa
    import fairplay_ropa
    import marathon_ropa
    import taf_ropa
except ImportError:
    st.error("⚠️ Faltan los archivos de Ropa (*_ropa.py). Verifica tu carpeta.")

# --- IMPORT REPORT GENERATOR ---
import reporter

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Nike Bolivia Analytics",
    page_icon="👟",
    layout="wide"
)

# --- SESSION STATE INITIALIZATION (PARA QUE NO SE BORRE LA DATA) ---
if 'data_results' not in st.session_state:
    st.session_state.data_results = None

# --- HELPER FUNCTIONS ---
def run_clothing_scraper(gender):
    """Ejecuta los scrapers de ropa usando los módulos dedicados (*_ropa.py)"""
    results = []
    url_fp, url_ms, url_yuth, url_taf = utils_ropa.generate_urls(gender)
    
    if url_fp:
        st.write(f"   • Escaneando Fairplay (Ropa - {gender})...")
        results.extend(fairplay_ropa.scrape(url_fp, "Ropa", "Indumentaria", gender, store_name='Fairplay'))
    if url_yuth:
        st.write(f"   • Escaneando Yuth (Ropa - {gender})...")
        results.extend(fairplay_ropa.scrape(url_yuth, "Ropa", "Indumentaria", gender, store_name='Yuth'))
    if url_taf:
        st.write(f"   • Escaneando TAF (Ropa - {gender})...")
        results.extend(taf_ropa.scrape(url_taf, "Ropa", "Indumentaria", gender))
    if url_ms:
        st.write(f"   • Escaneando Marathon (Ropa - {gender})...")
        results.extend(marathon_ropa.scrape(url_ms, "Ropa", "Indumentaria", gender))
    return results

def run_footwear_scraper(gender, sport_key):
    """Ejecuta los scrapers de calzado usando los módulos estándar (*_scraper.py)"""
    results = []
    url_fp, url_ms, url_yuth, url_taf = utils.generate_urls(sport_key, gender, 'calzado')
    
    if url_fp:
        st.write(f"   • Fairplay ({gender} - {sport_key})...")
        results.extend(fairplay_scraper.scrape(url_fp, sport_key, sport_key, gender, store_name='Fairplay'))
    if url_yuth:
        st.write(f"   • Yuth ({gender} - {sport_key})...")
        results.extend(fairplay_scraper.scrape(url_yuth, sport_key, sport_key, gender, store_name='Yuth'))
    if url_taf:
        st.write(f"   • TAF ({gender} - {sport_key})...")
        results.extend(taf_scraper.scrape(url_taf, sport_key, sport_key, gender))
    if url_ms:
        st.write(f"   • Marathon ({gender} - {sport_key})...")
        results.extend(marathon_scraper.scrape(url_ms, sport_key, sport_key, gender))
    return results

# --- SIDEBAR & NAVIGATION ---
with st.sidebar:
    st.title("👟 Configuración")
    
    mode = st.radio(
        "Modo de Extracción:",
        ["🎯 Búsqueda Específica", "🌐 EXTRACCIÓN TOTAL"],
        help="Específica: Busca una categoría puntual. Total: Descarga TODO el catálogo."
    )
    
    st.markdown("---")
    
    selected_gender = "hombre"
    selected_type = "calzado"
    selected_sport = "correr"
    
    if mode == "🎯 Búsqueda Específica":
        st.subheader("Filtros")
        g_disp = st.selectbox("1. Género", ["Hombre", "Mujer"])
        selected_gender = g_disp.lower()
        
        t_disp = st.selectbox("2. Tipo", ["Calzado", "Ropa (Todo)"])
        
        if "Ropa" in t_disp:
            selected_type = "ropa"
            st.info("ℹ️ El modo 'Ropa' realizará un barrido completo de la indumentaria.")
        else:
            selected_type = "calzado"
            sport_map = {
                "Correr": "correr", "Futbol": "futbol", "Entrenamiento": "entrenamiento",
                "Tenis": "tenis", "Basquet": "basquet", "Lifestyle (Urbano)": "lifestyle"
            }
            s_disp = st.selectbox("3. Deporte", list(sport_map.keys()))
            selected_sport = sport_map[s_disp]
            
        start_btn = st.button("🚀 INICIAR BÚSQUEDA", type="primary", use_container_width=True)
        
    else: # EXTRACCIÓN TOTAL
        st.warning("⚠️ ¡ATENCIÓN! Esto tomará varios minutos.")
        start_btn = st.button("☢️ EJECUTAR SCRAPER COMPLETO", type="primary", use_container_width=True)

# --- MAIN PAGE LOGIC ---

st.title("👟 Nike Bolivia - Market Analyzer")

# --- SCRAPING EXECUTION ---
if start_btn:
    # Limpiamos la sesión anterior
    st.session_state.data_results = None
    all_data = []
    
    progress_container = st.status("🔄 Iniciando proceso...", expanded=True)
    
    try:
        if mode == "🎯 Búsqueda Específica":
            with progress_container:
                if selected_type == "ropa":
                    st.write(f"📍 Iniciando modo ROPA para {selected_gender.upper()}...")
                    all_data = run_clothing_scraper(selected_gender)
                else:
                    st.write(f"📍 Iniciando modo CALZADO ({selected_sport}) para {selected_gender.upper()}...")
                    all_data = run_footwear_scraper(selected_gender, selected_sport)
                progress_container.update(label="✅ ¡Búsqueda finalizada!", state="complete", expanded=False)

        else: # FULL MODE
            with progress_container:
                genders = ['hombre', 'mujer']
                sports = ['correr', 'futbol', 'entrenamiento', 'tenis', 'basquet', 'lifestyle']
                
                for g in genders:
                    st.write(f"📍 [{g.upper()}] Escaneando TODA LA ROPA...")
                    all_data.extend(run_clothing_scraper(g))
                    for s in sports:
                        st.write(f"📍 [{g.upper()}] Escaneando CALZADO - {s.upper()}...")
                        all_data.extend(run_footwear_scraper(g, s))
                progress_container.update(label="✅ ¡EXTRACCIÓN TOTAL COMPLETADA!", state="complete", expanded=False)

        # GUARDAR EN SESSION STATE
        if all_data:
            df = pd.DataFrame(all_data)
            cols = ['Tienda', 'Genero', 'Deporte', 'Producto', 'Marca', 'Modelo', 'SKU', 'Precio Regular (Bs)', 'Descuento (%)', 'Precio Final (Bs)', 'Link']
            for c in cols: 
                if c not in df.columns: df[c] = ""
            
            # Limpieza básica
            df['SKU'] = df['SKU'].astype(str).str.strip()
            df_clean = df.drop_duplicates(subset=['Tienda', 'SKU'], keep='first')[cols]
            
            st.session_state.data_results = df_clean
        else:
            st.error("❌ No se encontraron productos.")
            st.session_state.data_results = None

    except Exception as e:
        st.error(f"❌ Ocurrió un error: {e}")

# --- DISPLAY RESULTS (FROM SESSION STATE) ---
if st.session_state.data_results is not None:
    df_clean = st.session_state.data_results
    
    # Metrics
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Productos", len(df_clean))
    c2.metric("Tiendas", df_clean['Tienda'].nunique())
    
    try:
        price_series = df_clean['Precio Final (Bs)'].astype(str).str.replace('.','', regex=False).str.replace(',','.', regex=False)
        avg = pd.to_numeric(price_series, errors='coerce').mean()
        c3.metric("Precio Promedio", f"Bs {avg:,.2f}")
    except:
        c3.metric("Precio Promedio", "N/A")

    # Table
    st.subheader("📊 Resultados")
    st.dataframe(df_clean)
    
    # Download Section
    st.markdown("### 📥 Descargas (Disponibles simultáneamente)")
    col_d1, col_d2 = st.columns(2)
    
    today = datetime.now().strftime('%Y-%m-%d_%H-%M')
    
    # 1. CSV Button
    csv = df_clean.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    fname_csv = f"Nike_Data_{today}.csv"
    
    col_d1.download_button(
        label="💾 Descargar Base de Datos (CSV)",
        data=csv,
        file_name=fname_csv,
        mime='text/csv'
    )
    
    # 2. PDF Report Button
    pdf_bytes = reporter.generate_comparison_pdf(df_clean, report_title="Reporte Nike vs Adidas")
    
    if pdf_bytes:
        col_d2.download_button(
            label="📄 Descargar Reporte PDF",
            data=pdf_bytes,
            file_name=f"Reporte_Ejecutivo_{today}.pdf",
            mime='application/pdf',
            type="primary"
        )
    else:
        col_d2.info("⚠️ Para generar el reporte PDF se necesitan datos de Nike y Adidas en la búsqueda.")