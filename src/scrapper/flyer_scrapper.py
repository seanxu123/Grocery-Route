from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from googletrans import Translator
import re
import requests
from PIL import Image
from io import BytesIO
from .cogvlm import generate_cogvlm_model, generate_name_and_price

vlm_model = generate_cogvlm_model()

def get_english_name(name: str) -> str:    
    translator = Translator()
    if "|" in name:
        english_name = name.split("|")[1].strip()
    else:
        english_name = translator.translate(name, src="fr", dest="en").text

    english_name = " ".join(
        word.capitalize() for word in re.split(r"\s+", english_name.strip())
    )

    return english_name


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


def fetch_image_from_url(url: str) -> Image:
    response = requests.get(url)
    
    if response.status_code == 200:
        image = Image.open(BytesIO(response.content))
        return image
    else:
        raise Exception(f"Failed to fetch image. Status code: {response.status_code}")


def handle_image_only_item(driver, product_url):
    try:
        item_image_url = driver.find_element(By.CSS_SELECTOR, 'div.item-info-image img').get_attribute('src')
        image = fetch_image_from_url(item_image_url)
        name, price = generate_name_and_price(vlm_model, image)
        
        if price is None:
            print(f"{product_url} is not a valid item")
            return None, None
        
        return name, price
    except Exception as e:
        print("Invalid item detected")
        return None, None
    

def fetch_item_price(driver, product_url, name):
    driver.get(product_url)
    wait = WebDriverWait(driver, 5)
    price_class = "flipp-price"
    unit_class = ".price-text"

    try:
        # Wait for specific element to load
        element = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, price_class))
        )

        price = driver.find_element(By.CSS_SELECTOR, price_class).get_attribute("value")

        unit_element = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, unit_class)
            )  # Adjust the selector as needed
        )
        unit = unit_element.text.strip()

        return name, price
    except (Exception, TimeoutException):
        #print(f"Error fetching product price for item: {product_url} with name: {name}")
        name, price = handle_image_only_item(driver, product_url)
        if price is None:
            return None, None
        
        return name, price


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

    subtitle_element = soup.find("span", class_="subtitle")
    store_name = (
        subtitle_element.get_text(strip=True) if subtitle_element else "Unknown Store"
    )
    print(f"Store name: {store_name}")

    name_class = "aria-label"
    item_class = "item-container"
    items = soup.find_all("a", class_=item_class)

    bullshit_words = ["Ajoutez", "Ecom", "economies", "Moi", "Format econo"]
    item_infos_list = []

    num_items = 0
    for item in items:
        item_name = item.get(name_class)
        
        if item_name not in bullshit_words and item_name:
            item_name = get_english_name(item_name)
            item_id = item.get("itemid")
            item_url = f"https://flipp.com/en-ca/pierrefonds-qc/item/{item_id}?postal_code=H8Y3P2"
            item_name, item_price = fetch_item_price(driver, item_url, item_name)

            if item_price is None:
               continue

            print(
                f"Id: {item_id}, Name: {item_name}, price: {item_price}, url: {item_url}"
            )

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
        EC.presence_of_element_located((By.CLASS_NAME, "flyer-container"))
    )
    soup = BeautifulSoup(driver.page_source, "html.parser")

    blacklisted_flyer_ids = [6710749]  # BulkBarn
    flyer_items = soup.find_all("flipp-flyer-listing-item")

    flyer_urls = []
    for item in flyer_items:
        if item.has_attr("flyer-id"):
            flyer_id = int(item["flyer-id"])
            if flyer_id not in blacklisted_flyer_ids:
                flyer_url = f"https://flipp.com/en-ca/pierrefonds-qc/flyer/{flyer_id}?postal_code=H8Y3P2"
                flyer_urls.append(flyer_url)

    # print(f"Flyer_urls: {flyer_urls}")
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


def test():
    print(f"Starting scrapper ...")
    
    homepage_url = (
        "https://flipp.com/en-ca/pierrefonds-qc/flyers/groceries?postal_code=H8Y3P2"
    )
    jean_coutu_url = "https://flipp.com/en-ca/pierrefonds-qc/item/860885398-jean-coutu-more-savings-flyer?postal_code=H8Y3P2"
    cnt_url = "https://flipp.com/en-ca/pierrefonds-qc/item/862797850-marche-c-and-t-weekly?postal_code=H8Y3P2"

    driver = setup_chrome_driver()
    extract_item_infos(driver, cnt_url)
    driver.quit()


if __name__ == "__main__":
    main()
    #test()
