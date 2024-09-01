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


def handle_image_only_item(driver):
    try:
        item_image_url = driver.find_element(By.CSS_SELECTOR, 'div.item-info-image img').get_attribute('src')
        print(f"{item_image_url} is an image only item")
        item_name, price, unit = get_flyer_image_infos(item_image_url)
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


def get_store_chain_name(soup, flyer_url):
    subtitle_element = soup.find("span", class_="subtitle")
    store_chain_name = (
        subtitle_element.get_text(strip=True) if subtitle_element else "Unknown Store"
    )
    print(f"Store chain name: {store_chain_name}")
    
    #Assign store chain to flyer record
    '''
    insert_value_in_column(
        value = store_chain_name,
        column="store_chain",
        table="flyer",
        engine=engine
    )
    '''
    return store_chain_name


def get_item_name(item):
    bullshit_words = ["Ajoutez", "Ecom", "economies", "Moi", "Format econo"]
    name_class = "aria-label"
    
    item_name = item.get(name_class)
    if item_name not in bullshit_words and item_name:
        item_name = get_english_name(item_name)
        
    return item_name
    

def extract_item_infos(driver, flyer_url, flyer_id):
    driver.get(flyer_url)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "item-container"))
        )
    except Exception as e:
        print(f"Error, can't find items in flyer: {flyer_url}: {e}")
        extract_item_infos(driver, flyer_url)
        return
        
    soup = BeautifulSoup(driver.page_source, "html.parser")
    get_store_chain_name(soup, flyer_url)

    item_class = "item-container"
    items = soup.find_all("a", class_=item_class)

    num_items = 0
    for item in items:
        product_id = item.get("itemid")
        item_url = f"https://flipp.com/en-ca/pierrefonds-qc/item/{product_id}?postal_code=H8Y3P2"
        
        try:
            price, unit = fetch_item_price_and_unit(driver, item_url)
            product_name = get_item_name(item)
        except Exception as e:
            #print(f"Product {item_url} is an image only item")
            product_name, price, unit = handle_image_only_item(driver)
            if product_name is None:
                continue

        print(f"product id: {product_id}, product_name: {product_name}, price: {price}, unit: {unit},  url: {item_url}")

        product_infos = {
            "product id": product_id,
            "product_name": product_name,
            "price": price,
            "unit": unit,
            "url": item_url,
            "flyer_id": flyer_id
        }
        
        '''
        insert_product_record(
            product_infos=product_infos,
            table="products",
            engine=engine
        )
        '''

        num_items += 1
        if num_items == 2:
            break


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


def extract_flyer_end_date(item):
    validity_element = item.find("span", class_="validity")
    
    if validity_element:
        validity_text = validity_element.get_text(strip=True)
        end_date = parse_end_date(validity_text)
    else:
        end_date = None
    
    return end_date


def get_flyer_infos(driver, homepage_url):
    driver.get(homepage_url)
    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.TAG_NAME, "flipp-flyer-listing-item"))
    )
    soup = BeautifulSoup(driver.page_source, "html.parser")

    
    flyer_items = soup.find_all("flipp-flyer-listing-item")

    flyer_infos = []
    for item in flyer_items:
        if item.has_attr("flyer-id"):
            flyer_id = int(item["flyer-id"])
            flyer_url = f"https://flipp.com/en-ca/pierrefonds-qc/flyer/{flyer_id}?postal_code=H8Y3P2"
            end_date = extract_flyer_end_date(
                item=item
            )
            
            '''
            insert_flyer_record(
                flyer_id=flyer_id,
                flyer_url=flyer_url,
                valid_until=end_date,
                table="flyer",
                engine=engine
            )
            '''
            
            flyer_infos.append({"flyer_url": flyer_url, "flyer_id": flyer_id})
    
    return flyer_infos


def get_all_items_infos(driver, homepage_url):
    flyer_infos = get_flyer_infos(driver, homepage_url)

    for flyer in flyer_infos:
        print()
        flyer_url = flyer["flyer_url"]
        flyer_id = flyer["flyer_id"]
        print(f"Extracting items from flyer_url: {flyer_url}")
        extract_item_infos(driver, flyer_url, flyer_id)


def main():
    print(f"Starting scrapper ...")
    homepage_url = (
        "https://flipp.com/en-ca/pierrefonds-qc/flyers/groceries?postal_code=H8Y3P2"
    )

    driver = setup_chrome_driver()
    get_all_items_infos(driver, homepage_url)
    driver.quit()


if __name__ == "__main__":
    main()
