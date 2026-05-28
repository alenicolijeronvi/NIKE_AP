import re
from bs4 import BeautifulSoup
import utils_ropa as utils
import concurrent.futures

def get_product_and_variants(url, category_label, sport_label, gender_label):
    product_data = None
    found_variant_urls = set()
    
    try:
        html = utils.fetch_html(url, add_desktop=True)
        if not html: return None, []
        
        soup = BeautifulSoup(html, 'html.parser')
        
        name_tag = soup.select_one('.product-details .name, h1, .product__name')
        full_name = name_tag.get_text(strip=True) if name_tag else "Desconocido"
        
        if not utils.is_valid_product(full_name, gender_label):
            return None, []

        brand, model = utils.split_brand_model(full_name)

        # Precios
        raw_price = "0"
        price_tags = soup.select('.item-content-price, .price .value, .product__price, .price')
        for tag in price_tags:
            text = tag.get_text(strip=True)
            if text and any(c.isdigit() for c in text):
                raw_price = text
                break
        p_reg_float = utils.clean_price_marathon(raw_price)
        
        discount = 0
        discount_nodes = soup.find_all(string=re.compile(r'(\d+)\s*%\s*(de\s*)?Descuento', re.IGNORECASE))
        if discount_nodes:
            for node in discount_nodes:
                match = re.search(r'(\d+)', node)
                if match:
                    val = int(match.group(1))
                    if val > discount: discount = val

        p_fin_float = p_reg_float
        if discount > 0:
            p_fin_float = p_reg_float * (1 - (discount / 100.0))

        str_reg = utils.format_price_excel(p_reg_float)
        str_fin = utils.format_price_excel(p_fin_float)

        # SKU
        current_sku = "N/A"
        text_nodes = soup.find_all(string=re.compile(r'ID', re.IGNORECASE))
        for text in text_nodes:
            clean_text = text.strip()
            if len(clean_text) < 30 and any(c.isdigit() for c in clean_text):
                candidate = re.sub(r'(?i)ID|[:|]', '', clean_text).strip()
                if len(candidate) > 3:
                    current_sku = candidate
                    break
        
        if current_sku == "N/A" and '/p/' in url:
             try: current_sku = url.split('/p/')[-1].split('/')[0].split('?')[0]
             except: pass

        if p_fin_float > 0 and current_sku != "N/A":
            product_data = {
                'Tienda': 'Marathon',
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

        selectors = ['.variant-list a', '.swatch-list a', '.item-color a', 'div[class*="swatch"] a']
        for sel in selectors:
            links = soup.select(sel)
            for link in links:
                href = link.get('href')
                if href and '/p/' in href:
                    full_link = f"https://www.marathon.store{href}" if href.startswith('/') else href
                    found_variant_urls.add(full_link.split('?')[0])
                    
    except Exception as e: pass
    return product_data, list(found_variant_urls)

def scrape(url, category_label, sport_label, gender_label):
    all_products = []
    visited_urls = set()
    url_queue = [] 
    queue_set = set()
    
    try:
        print(f"\n--- Iniciando Marathon (ROPA GENERAL): {gender_label} ---")
        current_url = url
        max_listing_pages = 50 
        page_count = 0
        
        while current_url and page_count < max_listing_pages:
            html = utils.fetch_html(current_url, add_desktop=True)
            if not html: break
            
            soup = BeautifulSoup(html, 'html.parser')
            items = soup.select('.product-item, .product__listing .product__list--item')
            items_found_on_page = 0
            
            for item in items:
                main_links = item.select('a[href*="/p/"]')
                for link_tag in main_links:
                    href = link_tag.get('href')
                    if href:
                        full_link = f"https://www.marathon.store{href}" if href.startswith('/') else href
                        clean_link = full_link.split('?')[0]
                        if clean_link not in queue_set:
                            url_queue.append(clean_link)
                            queue_set.add(clean_link)
                            items_found_on_page += 1
            
            print(f"    Página {page_count+1}: {items_found_on_page} items detectados.")
            if items_found_on_page == 0: break

            page_count += 1
            next_url = None
            next_btn = soup.select_one('.pagination-next > a, a[rel="next"], li.next a')
            if next_btn:
                raw = next_btn.get('href')
                if raw and raw != "#":
                    if raw.startswith('http'): next_url = raw
                    elif raw.startswith('/'): next_url = "https://www.marathon.store" + raw
                    else: 
                        base = current_url.split('?')[0]
                        next_url = f"{base}{raw}" if '?' in base else f"{current_url}{raw}"
            current_url = next_url

        print(f"  - Extrayendo datos de {len(url_queue)} items...")
        
        def process_link(link):
            if link not in visited_urls:
                data, variants = get_product_and_variants(link, category_label, sport_label, gender_label)
                return link, data, variants
            return link, None, []

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(process_link, url): url for url in url_queue}
            i = 0
            for future in concurrent.futures.as_completed(future_to_url):
                link, data, variants = future.result()
                if data:
                    all_products.append(data)
                visited_urls.add(link)
                for v in variants:
                    if v not in queue_set:
                        queue_set.add(v)
                i += 1
                pct = i / len(url_queue) * 100
                print(f"    Visitando: {i}/{len(url_queue)} ({pct:.1f}%)", end='\r')

    except Exception as e:
        print(f"\n❌ Error en Marathon: {e}")
    finally:
        print(f"\n✅ Marathon finalizado: {len(all_products)} items.")
    return all_products