import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
import io
from datetime import datetime
import numpy as np

# Configuración visual
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = (11, 7)
plt.rcParams['font.family'] = 'sans-serif'

# --- LISTA DE ALIAS DE NIKE ---
NIKE_ALIASES = {
    'M', 'JORDAN', 'CHELSEA', 'PSG', 'LEBRON', 'FFF', 'ATLÉTICO', 'CFC', 
    'CBF', 'LFC', 'KOBE', 'PARIS', 'LIVERPOOL', 'PRIMERA', 'LOS', 'W', 
    'WMNS', 'AIR', 'KILLSHOT', 'BLAZER', 'ZOOMX', 'COSMIC', 'LEGEND', 'ZOOM', 'NIKE'
}

def clean_currency(val):
    """Limpia el formato de moneda a float"""
    if isinstance(val, (int, float)): return val
    s = str(val).replace('Bs', '').replace(' ', '')
    s = s.replace('.', '') 
    s = s.replace(',', '.') 
    try: return float(s)
    except: return 0.0

def normalize_brand_for_report(brand_name):
    """Normaliza las marcas solo para el reporte"""
    if not brand_name: return "Desconocido"
    b_upper = str(brand_name).upper().strip()
    if b_upper in NIKE_ALIASES: return 'Nike'
    if 'NIKE' in b_upper: return 'Nike'
    if 'ADIDAS' in b_upper: return 'Adidas'
    return brand_name.title()

def get_stats_dict(series):
    """Calcula métricas estadísticas completas para una serie de precios"""
    desc = series.describe()
    Q1 = desc['25%']
    Q3 = desc['75%']
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    outliers = series[(series < lower_bound) | (series > upper_bound)]
    skew = series.skew()
    
    return {
        'min': desc['min'],
        'q1': Q1,
        'median': desc['50%'],
        'q3': Q3,
        'max': desc['max'],
        'mean': desc['mean'], # Promedio aritmético
        'std': desc['std'],
        'iqr': IQR,
        'skew': skew,
        'outliers_count': len(outliers),
        'outliers_limit': upper_bound
    }

def interpret_skew(skew):
    """Interpreta el coeficiente de asimetría"""
    if skew > 1: return "un fuerte sesgo positivo (cola hacia precios altos)"
    elif skew > 0.5: return "un sesgo positivo moderado"
    elif skew < -0.5: return "un sesgo negativo"
    else: return "una distribución simétrica"

def generate_comparison_pdf(df_original, report_title="Reporte Comparativo", category_subtitle="General"):
    if df_original.empty: return None

    # --- 1. PREPARACIÓN DE DATOS ---
    df = df_original.copy()
    df['Marca_Reporte'] = df['Marca'].apply(normalize_brand_for_report)
    df['Precio_Num'] = df['Precio Final (Bs)'].apply(clean_currency)
    
    # Filtro: Solo Nike y Adidas
    df_report = df[df['Marca_Reporte'].isin(['Nike', 'Adidas'])].copy()
    if df_report.empty: return None

    pdf_buffer = io.BytesIO()
    
    # Colores: Nike (Naranja), Adidas (Gris Oscuro)
    palette = {'Nike': '#F35325', 'Adidas': '#4a4a4a'} 

    with PdfPages(pdf_buffer) as pdf:
        
        # =========================================================================
        # PÁGINA 1: ANÁLISIS ESTADÍSTICO Y NARRATIVA
        # =========================================================================
        plt.figure(figsize=(8.5, 11)) # Carta Vertical
        plt.axis('off')
        
        # Encabezado (Top 15% de la página)
        plt.text(0.5, 0.95, "REPORTE DE PRECIOS: NIKE vs ADIDAS", ha='center', fontsize=20, weight='bold', color='#2c3e50')
        plt.text(0.5, 0.92, f"Categoría Analizada: {category_subtitle.upper()}", ha='center', fontsize=12, weight='bold', color='#e67e22')
        plt.text(0.5, 0.89, f"Fecha de Generación: {datetime.now().strftime('%d/%m/%Y')}", ha='center', fontsize=10, color='gray')

        # --- CÁLCULOS Y GENERACIÓN DE NARRATIVA ---
        try:
            # Obtener diccionarios estadísticos
            nike_s = get_stats_dict(df_report[df_report['Marca_Reporte']=='Nike']['Precio_Num'])
            adidas_s = get_stats_dict(df_report[df_report['Marca_Reporte']=='Adidas']['Precio_Num'])
            
            # Comparativa Promedios (MEDIA) - Dato Solicitado
            diff_mean = ((nike_s['mean'] - adidas_s['mean']) / adidas_s['mean']) * 100
            diff_mean_str = "más caro" if diff_mean > 0 else "más barato"
            
            # Comparativa Medianas (Robustez)
            diff_median = ((nike_s['median'] - adidas_s['median']) / adidas_s['median']) * 100
            
            # Redacción del Párrafo de Análisis
            narrative = (
                f"ANÁLISIS DE INTELIGENCIA DE PRECIOS\n"
                f"----------------------------------------------------------\n\n"
                
                f"1. DIFERENCIAL DE PRECIO PROMEDIO (KPI):\n"
                f"En términos de ticket promedio, Nike es un {abs(diff_mean):.2f}% {diff_mean_str} que Adidas. "
                f"El precio medio de Nike se sitúa en Bs {nike_s['mean']:,.2f}, mientras que el de Adidas es de Bs {adidas_s['mean']:,.2f}. "
                f"Este indicador refleja el posicionamiento de valor percibido global.\n\n"
                
                f"2. RESUMEN DE 5 NÚMEROS Y ESTRUCTURA (Robustez):\n"
                f"Para eliminar el ruido de los valores extremos, analizamos la estructura de los cuartiles:\n"
                f"   • Nike:    Min Bs {nike_s['min']:.0f} | Q1 Bs {nike_s['q1']:.0f} | Mediana Bs {nike_s['median']:.0f} | Q3 Bs {nike_s['q3']:.0f} | Max Bs {nike_s['max']:.0f}\n"
                f"   • Adidas:  Min Bs {adidas_s['min']:.0f} | Q1 Bs {adidas_s['q1']:.0f} | Mediana Bs {adidas_s['median']:.0f} | Q3 Bs {adidas_s['q3']:.0f} | Max Bs {adidas_s['max']:.0f}\n"
                f"La mediana confirma la tendencia, mostrando una diferencia estructural del {abs(diff_median):.1f}%.\n\n"
                
                f"3. SESGO Y COMPORTAMIENTO DE LA CURVA:\n"
                f"Nike presenta {interpret_skew(nike_s['skew'])}. Esto implica que la mayoría de sus productos se concentran "
                f"cerca de la mediana, pero cuenta con una 'cola' de artículos de alto valor.\n"
                f"Adidas muestra {interpret_skew(adidas_s['skew'])}, con una dispersión de precios que abarca desde Bs {adidas_s['min']:,.0f} hasta Bs {adidas_s['max']:,.0f}.\n\n"
                
                f"4. VALORES ATÍPICOS (OUTLIERS):\n"
                f"El análisis detectó {nike_s['outliers_count']} productos de Nike por encima de Bs {nike_s['outliers_limit']:,.0f}. "
                f"Estos valores atípicos representan el segmento 'Ultra-Premium' o lanzamientos exclusivos."
            )
            
        except Exception as e:
            narrative = f"Datos insuficientes para generar el análisis narrativo completo.\nError: {e}"

        # Renderizar el texto (Ajustado: Empieza arriba y baja, centrado)
        # x=0.12 da un margen izquierdo más estético. y=0.82 empieza debajo del encabezado.
        plt.text(0.12, 0.82, narrative, fontsize=11, va='top', ha='left', wrap=True, family='sans-serif', linespacing=1.6)
        
        # Tabla resumen compacta al pie (Bottom 15-20%)
        y_table = 0.18
        plt.text(0.5, y_table + 0.03, "TABLA COMPARATIVA DE MÉTRICAS", ha='center', weight='bold')
        
        col_labels = ['Métrica', 'Nike', 'Adidas']
        cell_text = [
            ['Promedio (Mean)', f"Bs {nike_s['mean']:,.2f}", f"Bs {adidas_s['mean']:,.2f}"],
            ['Mediana (Median)', f"Bs {nike_s['median']:,.0f}", f"Bs {adidas_s['median']:,.0f}"],
            ['Mínimo', f"Bs {nike_s['min']:,.0f}", f"Bs {adidas_s['min']:,.0f}"],
            ['Máximo', f"Bs {nike_s['max']:,.0f}", f"Bs {adidas_s['max']:,.0f}"],
            ['Outliers (Cant.)', f"{nike_s['outliers_count']}", f"{adidas_s['outliers_count']}"]
        ]
        
        table = plt.table(cellText=cell_text, colLabels=col_labels, loc='bottom', bbox=[0.15, 0.05, 0.7, 0.15], cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.5)

        pdf.savefig()
        plt.close()

        # =========================================================================
        # PÁGINA 2: BOXPLOT VERTICAL
        # =========================================================================
        plt.figure(figsize=(11, 8))
        
        # Boxplot Vertical
        sns.boxplot(
            data=df_report, 
            x='Marca_Reporte', 
            y='Precio_Num', 
            palette=palette,
            width=0.5,
            linewidth=1.5,
            showmeans=True,
            meanprops={"marker":"o", "markerfacecolor":"white", "markeredgecolor":"black", "markersize": "8"}
        )
        
        # Stripplot
        sns.stripplot(
            data=df_report, 
            x='Marca_Reporte', 
            y='Precio_Num', 
            color=".2", 
            alpha=0.3, 
            size=3
        )
        
        plt.title(f"DISTRIBUCIÓN DE PRECIOS: {category_subtitle.upper()}", fontsize=16, weight='bold', pad=20)
        plt.ylabel("Precio Final (Bs)", fontsize=12)
        plt.xlabel("Marca", fontsize=12)
        plt.grid(axis='y', linestyle='--', alpha=0.6)
        
        plt.figtext(0.5, 0.02, "Referencia: El punto blanco indica el Promedio. La línea negra central es la Mediana. Los puntos oscuros son la densidad de productos.", 
                    ha="center", fontsize=10, style='italic', color='#555')
        
        pdf.savefig()
        plt.close()

    pdf_buffer.seek(0)
    return pdf_buffer