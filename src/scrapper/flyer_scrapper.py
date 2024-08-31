from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from googletrans import Translator
import re
from .vertexai import get_item_name_and_price

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
        prompt ="Tell me the name of the item in less than 5 words. What is the price of the item (no dollar sign, just a float)? "\
                "Directly tell me the answer, without saying the item is or the price is. "\
                "Separate the answers with a comma."
                
        item_name, price = get_item_name_and_price(item_image_url, prompt)
        return item_name, price
    except Exception as e:
        print(f"Could not process image: {e}")
        return None, None
    

def fetch_item_price(driver, product_url, name):
    driver.get(product_url)
    price_class = "flipp-price"
    unit_class = ".price-text"

    try:
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

        return name, price
    except (Exception, TimeoutException):
        print(f"{name} with url {product_url} is an image only product.")
        item_name, price = handle_image_only_item(driver)
        return item_name, price


def get_store_name(soup):
    subtitle_element = soup.find("span", class_="subtitle")
    store_name = (
        subtitle_element.get_text(strip=True) if subtitle_element else "Unknown Store"
    )
    print(f"Store name: {store_name}")
    return store_name


def get_item_name(item):
    bullshit_words = ["Ajoutez", "Ecom", "economies", "Moi", "Format econo"]
    name_class = "aria-label"
    
    item_name = item.get(name_class)
    if item_name not in bullshit_words and item_name:
        item_name = get_english_name(item_name)
        
    return item_name
    

def extract_item_infos(driver, flyer_url):
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
    store_name = get_store_name(soup)

    item_class = "item-container"
    items = soup.find_all("a", class_=item_class)

    item_infos_list = []

    num_items = 0
    for item in items:
        item_name = get_item_name(item)
        item_id = item.get("itemid")
        item_url = f"https://flipp.com/en-ca/pierrefonds-qc/item/{item_id}?postal_code=H8Y3P2"
        
        item_name, item_price = fetch_item_price(driver, item_url, item_name)

        if item_price is None:
            continue

        print(f"Item id: {item_id}, Name: {item_name}, price: {item_price}, url: {item_url}")

        item_infos = {
            "Id": item_id,
            "Name": item_name,
            "Price": item_price,
        }

        item_infos_list.append(item_infos)
        num_items += 1

        if num_items == 2:
            break


def get_flyer_urls(driver, homepage_url):
    driver.get(homepage_url)
    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.TAG_NAME, "flipp-flyer-listing-item"))
    )
    soup = BeautifulSoup(driver.page_source, "html.parser")

    
    flyer_items = soup.find_all("flipp-flyer-listing-item")

    flyer_urls = []
    for item in flyer_items:
        if item.has_attr("flyer-id"):
            flyer_id = int(item["flyer-id"])
            flyer_url = f"https://flipp.com/en-ca/pierrefonds-qc/flyer/{flyer_id}?postal_code=H8Y3P2"
            flyer_urls.append(flyer_url)
    
    return flyer_urls


def get_all_items_infos(driver, homepage_url):
    flyer_urls = get_flyer_urls(driver, homepage_url)

    num_stores = 0
    for flyer_url in flyer_urls:
        print()
        print(f"Extracting items from flyer_url: {flyer_url}")
        extract_item_infos(driver, flyer_url)

        num_stores += 1
        #if num_stores == 10:
        #    break


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
    #test()
