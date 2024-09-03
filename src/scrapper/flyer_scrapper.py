from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from googletrans import Translator
import re
from .vertexai import get_flyer_image_infos
from .database import *
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

engine = get_sql_engine_from_env()

def get_english_name(name: str) -> str:    
    if "|" in name:
        return name.split("|")[1].strip().title()
    
    translator = Translator()
    max_retries = 3
    
    for i in range(max_retries):
        try:
            english_name = translator.translate(name, src="fr", dest="en").text
            return " ".join(word.capitalize() for word in re.split(r"\s+", english_name.strip()))
        except AttributeError:
            print(f"Translation failed for '{name}'. Retrying...")
        except Exception as e:
            print(f"Unexpected error during translation: {e}")
    
    # If all retries fail, return the original name
    print(f"Translation failed after {max_retries} attempts. Returning original name.")
    return name


def setup_chrome_driver():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=2000,2000")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36"
    )
    driver = webdriver.Chrome(options=chrome_options)
    return driver


def get_product_image_url(driver, product_url, retries=2):
    for attempt in range(retries):
        try:
            driver.get(product_url)
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.item-info-image img'))
            )
            item_image_url = driver.find_element(By.CSS_SELECTOR, 'div.item-info-image img').get_attribute('src')
            return item_image_url
        except Exception as e:
            print(f"Error retrieving image URL from {product_url}: {e}. Retrying ({attempt + 1}/{retries})...")
    return None  


def handle_image_only_item(product_image_url):
    try:
        print(f"{product_image_url} is an image only item")
        item_name, price, unit = get_flyer_image_infos(product_image_url)
        return item_name, price, unit
    except Exception as e:
        print(f"Could not process image: {e}")
        return None, None, None


def fetch_item_price_and_unit(driver, product_url):
    driver.get(product_url)
    price_class = "flipp-price"
    unit_class = ".price-text"

    wait = WebDriverWait(driver, 5)
    element = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, price_class))
    )

    price = driver.find_element(By.CSS_SELECTOR, price_class).get_attribute("value")

    unit_element = wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, unit_class)
        )  
    )
    unit = unit_element.text.strip()
    
    if unit is None or unit == "":
        unit = "each"

    return price, unit


def get_store_chain_name(driver, flyer_url):
    driver.get(flyer_url)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "item-container"))
        )
    except Exception as e:
        print(f"Error, can't find store chain name: {flyer_url}: {e}")
        get_store_chain_name(driver, flyer_url)
        return
    
    soup = BeautifulSoup(driver.page_source, "html.parser")
    subtitle_element = soup.find("span", class_="subtitle")
    store_chain_name = (
        subtitle_element.get_text(strip=True) if subtitle_element else "Unknown Store"
    )
    return store_chain_name


def get_item_name(item):
    bullshit_words = ["Ajoutez", "Ecom", "economies", "Moi", "Format econo"]
    name_class = "aria-label"
    
    item_name = item.get(name_class)
    if item_name not in bullshit_words and item_name:
        item_name = get_english_name(item_name)
        
    return item_name


def process_item(item, flyer_id):
    product_id = item.get("itemid")
    if product_id is None:
        return False  # Skip if no product_id

    driver = setup_chrome_driver()
    product_url = f"https://flipp.com/en-ca/pierrefonds-qc/item/{product_id}?postal_code=H8Y3P2"
    product_image_url = get_product_image_url(driver, product_url)

    try:
        price, unit = fetch_item_price_and_unit(driver, product_url)
        product_name = get_item_name(item)
    except Exception:
        product_name, price, unit = handle_image_only_item(product_image_url)
        if product_name is None or float(price) <= 0:
            driver.quit()
            return False  # Skip invalid items
        
    print(f"Processed item - ID: {product_id}, Name: {product_name}, Price: {price}, Unit: {unit}, URL: {product_url}")
    product_infos = {
        "product_id": product_id,
        "product_name": product_name,
        "price": price,
        "unit": unit,
        "url": product_url,
        "product_image_url": product_image_url,
        "flyer_id": flyer_id
    }
    
    insert_product_record(
        product_infos=product_infos,
        table="product",
        engine=engine
    )
    
    driver.quit()
    return True
    

def extract_item_infos(driver, flyer_url, flyer_id, retries=2):
    driver.get(flyer_url)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "item-container"))
        )
    except Exception as e:
        print(f"Error, can't find items in flyer: {flyer_url}: {e}")
        if retries > 0:
            retries -= 1
            return extract_item_infos(driver, flyer_url, flyer_id, retries)
        else:
            return False
        
    soup = BeautifulSoup(driver.page_source, "html.parser")
    items = soup.find_all("a", class_="item-container")
    print(f"Found {len(items)} from flyer {flyer_url}")

    num_items = 0

    # Using ThreadPoolExecutor for multithreading
    with ThreadPoolExecutor(max_workers = 1) as executor:  # Adjust max_workers based on your requirements
        futures = {executor.submit(process_item, item, flyer_id): item for item in items}
        
        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing Items"):
            result = future.result()
            if result:
                num_items += 1
    
    print(f"Retrieved infos for all {num_items} items on flyer")
    return True


def parse_end_date(date_str):
    """Parse the end date from a validity string."""
    # Example date string: "Valid Aug 29, 2024 – Sep 4, 2024"
    match = re.search(r'Valid \w+ \d{1,2}, \d{4} – (\w+ \d{1,2}, \d{4})', date_str)
    if match:
        end_date_str = match.group(1)
        try:
            end_date = datetime.datetime.strptime(end_date_str, "%b %d, %Y").date()
            return end_date
        except ValueError as e:
            print(f"Date parsing error: {e}")
            return None
    return None


def fetch_flyer_page(driver, flyer_url):
    driver.get(flyer_url)
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "validity"))
        )
    except Exception as e:
        print(f"Error occured when fetching flyer page: {e}")
        flyer_html = fetch_flyer_page(driver, flyer_url)
        
    flyer_html = BeautifulSoup(driver.page_source, "html.parser")
    return flyer_html


def extract_flyer_end_date(item, driver, flyer_url):
    flyer_html = fetch_flyer_page(driver, flyer_url)
    validity_element = flyer_html.find("span", class_="validity")
    
    if validity_element:
        validity_text = validity_element.get_text(strip=True)
        end_date = parse_end_date(validity_text)
    else:
        end_date = None
    
    return end_date


def extract_flyer_infos_from_homepage(driver, homepage_url):
    driver.get(homepage_url)
    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.TAG_NAME, "flipp-flyer-listing-item"))
    )
    soup = BeautifulSoup(driver.page_source, "html.parser")

    flyer_items = soup.find_all("flipp-flyer-listing-item")
    print(f"Found {len(flyer_items)} flyers on the homepage.")
    
    for item in flyer_items:
        if item.has_attr("flyer-id"):
            flyer_id = int(item["flyer-id"])
            if flyer_exists(flyer_id=flyer_id, table="flyer", engine=engine):
                continue
            
            flyer_url = f"https://flipp.com/en-ca/pierrefonds-qc/flyer/{flyer_id}?postal_code=H8Y3P2"
            end_date = extract_flyer_end_date(item, driver, flyer_url)
            store_chain = get_store_chain_name(driver, flyer_url)      
            print(f"Flyer id: {flyer_id}, flyer_url: {flyer_url}, end_date: {end_date}, store_chain: {store_chain}")
            
            insert_flyer_record(
                flyer_id=flyer_id,
                flyer_url=flyer_url,
                valid_until=end_date,
                store_chain=store_chain,
                table="flyer",
                engine=engine
            )
            
            
def get_flyer_infos(driver, homepage_url):
    delete_old_flyers_and_products(
        product_table="product",
        flyer_table="flyer",
        engine=engine
    )
    
    extract_flyer_infos_from_homepage(driver=driver, homepage_url=homepage_url)
    flyer_infos = get_unretrieved_flyers(table="flyer", engine=engine)
    return flyer_infos
    

def get_all_items_infos(driver, homepage_url):
    flyer_infos = get_flyer_infos(driver, homepage_url)

    for flyer_id, flyer_url in tqdm(flyer_infos, desc="Processing Flyers"):
        print()
        print(f"Extracting items from flyer_url: {flyer_url}")
        if extract_item_infos(driver, flyer_url, flyer_id) == False:
            continue
        
        print(f"Updating flyer retrieved status for flyer_id: {flyer_id}")
        set_flyer_retrieved_to_true(
            flyer_id=flyer_id,
            table="flyer",
            engine=engine
        )


def main():
    print(f"Starting scrapper ...")
    homepage_url = "https://flipp.com/en-ca/pierrefonds-qc/flyers/groceries?postal_code=H8Y3P2"
    with setup_chrome_driver() as driver:
        get_all_items_infos(driver, homepage_url)
        

if __name__ == "__main__":
    main()
