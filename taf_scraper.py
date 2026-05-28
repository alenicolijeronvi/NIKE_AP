import re
from bs4 import BeautifulSoup
import scraper_utils as utils
import concurrent.futures

def get_product_and_variants(url, category_label, sport_label, gender_label):
    try:
        html = utils.fetch_html(url)
        if not html: return None, []
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # --- LIMPIEZA DE CÓDIGO ---
        for hidden in soup(['script', 'style', 'noscript', 'iframe', 'header', 'footer']):
            hidden.decompose()

        # --- TÍTULO (MODELO) ---
        title_tag = soup.find('h1')
        full_name = title_tag.get_text(strip=True) if title_tag else ""
        
        if not full_name:
            return None, []

        model = full_name

        # --- FILTRO BLACKLIST ---
        breadcrumbs = soup.select_one('.woocommerce-breadcrumb')
        bread_text = breadcrumbs.get_text().lower() if breadcrumbs else ""
        
        blacklist = ['media', 'calcetin', 'gorra', 'accesorios', 'crema', 'mochila', 'bolso', 'scuderia', 'junior', 'niño', 'niña']
        
        if any(bad in full_name.lower() for bad in blacklist) or any(bad in bread_text for bad in blacklist):
            return None, []

        if not utils.is_valid_product(full_name, gender_label):
            return None, []

        # --- EXTRACCIÓN MARCA ---
        brand = "Desconocido"
        target_markers = soup.find_all(['th', 'td', 'span', 'strong', 'li'], string=re.compile(r'Marca', re.IGNORECASE))
        
        for marker in target_markers:
            if marker.name == 'th':
                sibling = marker.find_next_sibling('td')
                if sibling:
                    brand = sibling.get_text(strip=True)
                    break
            
            parent_text = marker.parent.get_text(strip=True)
            if 'Marca:' in parent_text:
                clean_text = parent_text.replace('Marca:', '').strip()
                brand = clean_text.split(',')[0].strip()
                break

        if brand == "Desconocido":
            meta_div = soup.select_one('.product_meta')
            if meta_div:
                match = re.search(r'Marca:\s*([^\n\r]+)', meta_div.get_text(), re.IGNORECASE)
                if match: brand = match.group(1).strip()

        if brand != "Desconocido":
            brand = brand.replace(',', '').strip()

        # --- EXTRACCIÓN PRECIOS ---
        raw_regular = "0"
        raw_final = "0"
        
        # Buscar el primer contenedor de precio que tenga montos (para evitar etiquetas vacías)
        price_container = None
        for p_cont in soup.select('.price'):
            if p_cont.select('.amount'):
                price_container = p_cont
                break
        
        if price_container:
            del_tag = price_container.select_one('del .amount')
            ins_tag = price_container.select_one('ins .amount')
            all_amounts = price_container.select('.amount')

            if del_tag and ins_tag:
                raw_regular = del_tag.get_text(strip=True)
                raw_final = ins_tag.get_text(strip=True)
            elif all_amounts:
                raw_final = all_amounts[-1].get_text(strip=True)
                raw_regular = raw_final
            
        p_fin_float = utils.clean_price_taf(raw_final)
        p_reg_float = utils.clean_price_taf(raw_regular)
        
        if p_reg_float < p_fin_float and p_reg_float > 0: p_reg_float = p_fin_float
        if p_reg_float == 0 and p_fin_float > 0: p_reg_float = p_fin_float
        
        discount = 0
        if p_reg_float > p_fin_float:
            try: discount = int(round((1 - (p_fin_float / p_reg_float)) * 100))
            except: pass
            
        str_reg = utils.format_price_excel(p_reg_float)
        str_fin = utils.format_price_excel(p_fin_float)

        # --- SKU (ESTRICTO: REQUIERE DOS PUNTOS ":") ---
        current_sku = "N/A"
        
        sku_candidates = soup.find_all(string=re.compile(r"Color", re.IGNORECASE))
        
        for candidate in sku_candidates:
            text_context = candidate.parent.get_text(" ", strip=True)
            
            if len(text_context) < 15: 
                try:
                    text_context = candidate.parent.parent.get_text(" ", strip=True)
                except: pass

            match = re.search(r'Color\s*:\s*([A-Z0-9\-\.]+)', text_context, re.IGNORECASE)
            
            if match:
                extracted = match.group(1).strip()
                extracted = extracted.rstrip('.')
                
                bad_words = ['var', 'transparent', 'select', 'color', 'elegir', 'opción', 'undefined', 'null']
                
                if len(extracted) >= 3 and extracted.lower() not in bad_words:
                    current_sku = extracted
                    break
        
        # Fallback URL
        if current_sku == "N/A":
            parts = url.strip('/').split('/')
            if parts: current_sku = parts[-1]

        if p_fin_float <= 0: 
            return None, []

        product_data = {
            'Tienda': 'TAF',
            'Genero': gender_label.capitalize(),
            'Deporte': sport_label.capitalize(), 
            'Producto': category_label.capitalize(), 
            'Marca': brand,
            'Modelo': model,
            'SKU': current_sku, 
            'Precio Regular (Bs)': str_reg,
            'Descuento (%)': discount,
            'Precio Final (Bs)': str_fin,
            'Link': url
        }

        # Variantes
        found_variants = []
        variant_area = soup.select('.variations, .swatches, .taf-swatch, table.variations')
        for area in variant_area:
            links = area.find_all('a', href=True)
            for l in links:
                v_href = l.get('href', '')
                if 'http' in v_href and v_href != url:
                    found_variants.append(v_href)

        return product_data, found_variants

    except Exception as e: 
        print(f"      ❌ Error extrayendo {url}: {e}")
        return None, []

def scrape(url, category_label, sport_label, gender_label):
    all_products = []
    
    try:
        print(f"\n--- Iniciando TAF: {gender_label} ---")
        
        current_page_url = url
        visited_urls = set()
        product_queue = []
        page_num = 1
        max_pages = 25 
        
        while current_page_url and page_num <= max_pages:
            html = utils.fetch_html(current_page_url)
            if not html: break
            
            soup = BeautifulSoup(html, 'html.parser')
            
            found_on_page = 0
            potential_links = []
            
            product_cards = soup.select('.product, .type-product, .product-small, li.product')
            
            if product_cards:
                for card in product_cards:
                    anchor = card.select_one('a.woocommerce-LoopProduct-link, .box-image a, .name a')
                    if not anchor:
                        anchor = card.find('a', href=True)
                    
                    if anchor and anchor.has_attr('href'):
                        potential_links.append(anchor['href'])
            else:
                all_a = soup.find_all('a', href=True)
                potential_links = [a['href'] for a in all_a]

            for href in potential_links:
                full_link = href if href.startswith('http') else f"https://www.taf.com.bo{href}"
                full_link = full_link.split('#')[0].split('?')[0]
                
                if full_link.rstrip('/') == 'https://taf.com.bo' or full_link == 'https://taf.com.bo/': continue
                
                bad_keywords = ['my-account', 'cart', 'checkout', 'add-to-cart', 'wishlist', 'login', 'wp-admin', 'logout', 'lost-password']
                if any(x in full_link for x in bad_keywords): continue

                if full_link not in visited_urls and full_link != current_page_url:
                    product_queue.append(full_link)
                    visited_urls.add(full_link)
                    found_on_page += 1

            print(f"    Página {page_num} cargada: {found_on_page} nuevos productos detectados.", end='\r')
            
            next_btn = soup.select_one('.next.page-numbers, a.next, .pagination-next')
            if next_btn: 
                current_page_url = next_btn.get('href')
                page_num += 1
            else: 
                try:
                    next_elements = soup.find_all('a', href=True)
                    found_next = False
                    for el in next_elements:
                        if '>' in el.get_text() or 'Siguiente' in el.get_text():
                            current_page_url = el['href']
                            page_num += 1
                            found_next = True
                            break
                    if not found_next: break
                except: break

        print(f"\n  - Iniciando extracción de {len(product_queue)} productos potenciales...")
        
        valid_count = 0
        
        def process_url(link):
            return get_product_and_variants(link, category_label, sport_label, gender_label)
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(process_url, link): link for link in product_queue}
            for i, future in enumerate(concurrent.futures.as_completed(future_to_url)):
                pct = (i+1)/len(product_queue)*100
                print(f"      Procesando: {i+1}/{len(product_queue)} ({pct:.1f}%)", end='\r')
                p_data, variants = future.result()
                
                if p_data: 
                    all_products.append(p_data)
                    valid_count += 1
                
                for v in variants:
                    if v not in visited_urls:
                        product_queue.append(v)
                        visited_urls.add(v)
                        executor.submit(process_url, v)

    except Exception as e:
        print(f"\n❌ Error fatal en TAF: {e}")
    finally:
        print(f"\n✅ TAF finalizado: {valid_count} registros válidos.")
        
    return all_products