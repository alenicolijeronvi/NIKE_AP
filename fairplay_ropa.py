from urllib.parse import urlparse
from bs4 import BeautifulSoup
import utils_ropa as utils
import concurrent.futures

def get_product_details(url, category_label, sport_label, gender_label, store_name):
    products = []
    try:
        html = utils.fetch_html(url)
        if not html: return []

        soup = BeautifulSoup(html, 'html.parser')
        
        name_tag = soup.find('span', class_=lambda x: x and 'productName' in x)
        if not name_tag: name_tag = soup.find('h1')
        if not name_tag: return []

        full_name = name_tag.get_text(strip=True)
        if not utils.is_valid_product(full_name, gender_label):
            return []

        brand, model = utils.split_brand_model(full_name)

        # Precios
        selling_tag = soup.find('span', class_=lambda x: x and 'sellingPriceValue' in x)
        if not selling_tag: selling_tag = soup.find('span', class_=lambda x: x and 'currencyContainer' in x)
        raw_final = selling_tag.get_text(strip=True) if selling_tag else "0"

        list_tag = soup.find('span', class_=lambda x: x and 'listPriceValue' in x)
        raw_regular = list_tag.get_text(strip=True) if list_tag else raw_final

        p_fin_float = utils.clean_price_fairplay(raw_final)
        p_reg_float = utils.clean_price_fairplay(raw_regular)
        
        if p_reg_float == 0 and p_fin_float > 0: p_reg_float = p_fin_float
        
        discount = 0
        if p_reg_float > p_fin_float:
            discount = int(round((1 - (p_fin_float / p_reg_float)) * 100))
            
        str_reg = utils.format_price_excel(p_reg_float)
        str_fin = utils.format_price_excel(p_fin_float)

        # SKU
        current_sku = "N/A"
        ref_span = soup.find('span', class_=lambda x: x and 'productReference' in x)
        if ref_span:
            raw_sku = ref_span.get_text(strip=True)
            current_sku = raw_sku.replace('Ref.:', '').replace('Referencia', '').replace(':', '').strip()
        
        if current_sku == "N/A":
            meta_sku = soup.find('meta', property='product:retailer_item_id')
            if meta_sku: current_sku = meta_sku.get('content')

        if p_fin_float > 0:
            products.append({
                'Tienda': store_name,
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
            })

    except: pass
    return products

def scrape(url, category_label, sport_label, gender_label, store_name='Fairplay'):
    all_products = []
    
    parsed_uri = urlparse(url)
    base_domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
    
    try:
        print(f"\n--- Iniciando {store_name} (ROPA GENERAL): {gender_label} ---")

        print("  - Escaneando catálogo completo...")
        model_urls = set()
        
        page = 1
        max_pages = 50
        while page <= max_pages:
            paginated_url = f"{url}&page={page}" if '?' in url else f"{url}?page={page}"
            html = utils.fetch_html(paginated_url)
            if not html: break
            
            if "no encontramos resultados" in html.lower():
                break

            soup = BeautifulSoup(html, 'html.parser')
            gallery_items = soup.select('.vtex-search-result-3-x-galleryItem')
            
            current_links = []
            if gallery_items:
                for item in gallery_items:
                    link = item.find('a', href=True)
                    if link: current_links.append(link)
            else:
                current_links = soup.select('a[href*="/p"]')

            if not current_links:
                break

            for link in current_links:
                href = link.get('href')
                if href and not any(x in href for x in ['login', 'wishlist', 'checkout', 'cart']):
                    full = f"{base_domain}{href}" if href.startswith('/') else href
                    base_link = full.split('?')[0] 
                    model_urls.add(base_link)
            
            print(f"    Página {page} cargada. (Encontrados: {len(model_urls)})", end='\r')
            page += 1

        total_models = len(model_urls)
        print(f"\n  - {total_models} prendas encontradas. Extrayendo datos...")
        
        url_list = list(model_urls)
        
        def process_url(link):
            return get_product_details(link, category_label, sport_label, gender_label, store_name)
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(process_url, link): link for link in url_list}
            for i, future in enumerate(concurrent.futures.as_completed(future_to_url)):
                pct = (i+1)/total_models*100
                if i % 5 == 0 or i == total_models - 1:
                    print(f"    Procesando: {i+1}/{total_models} ({pct:.1f}%)", end='\r')
                variants = future.result()
                if variants:
                    all_products.extend(variants)

    except Exception as e:
        print(f"\n❌ Error en {store_name}: {e}")
    finally:
        print(f"\n✅ {store_name} finalizado: {len(all_products)} items.")
        
    return all_products