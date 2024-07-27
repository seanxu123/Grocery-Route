from selenium import webdriver
from bs4 import BeautifulSoup
from collections import Counter
from googletrans import Translator
import re
import requests
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


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
    # chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=2000,2000")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36"
    )
    driver = webdriver.Chrome(options=chrome_options)
    return driver


def load_webpage_content(driver, url: str):
    driver.get(url)

    # Wait for dynamic content to load if necessary
    driver.implicitly_wait(10)

    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    return soup


def fetch_item_price(driver, product_url):
    driver.get(product_url)
    wait = WebDriverWait(driver, 10)
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

        return price, unit
    except Exception as e:
        print(f"Error fetching product price: {e}")


def extract_item_infos(driver, soup):
    bullshit_words = ["Ajoutez", "Ecom", "economies", "Moi", "Format econo"]

    name_class = "aria-label"
    item_class = "item-container"
    items = soup.find_all("a", class_=item_class)

    item_infos_list = []

    num_items = 0
    for item in items:
        item_name = item.get(name_class)

        if item_name not in bullshit_words and item_name:
            item_name = get_english_name(item_name)
            item_id = item.get("itemid")
            item_url = f"https://flipp.com/en-ca/pierrefonds-qc/item/{item_id}-super-c-flyer?postal_code=H8Y3P2"
            item_price, unit = fetch_item_price(driver, item_url)
            print(
                f"Id: {item_id}, Name: {item_name}, price: {item_price}, unit: {unit}, url: {item_url}"
            )

            item_infos = {
                "Id": item_id,
                "Name": item_name,
                "Price": item_price,
                "Unit": unit,
            }

            item_infos_list.append(item_infos)
            num_items += 1

        if num_items == 5:
            break


"""
def get_flyer_links(driver, homepage_url):
    driver.get(homepage_url)
    wait = WebDriverWait(driver, 10)

    flyer_class = "flyer-container"
    try:
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, f"a.{flyer_class}"))
        )
        flyers = driver.find_elements(By.CSS_SELECTOR, f"a.{flyer_class}")

        flyer_links = []
        for flyer in flyers:
            href = flyer.get_attribute("href")
            flyer_links.append(href)
            print(f"Flyer URL: {href}")

        return flyer_links
    except Exception as e:
        print(f"Error fetching flyer links: {e}")
        return []
"""


def get_flyer_links(driver, homepage_url):
    driver.get(homepage_url)
    wait = WebDriverWait(driver, 10)

    flyer_class = "flyer-container"
    flyer_links = []

    try:
        # Scroll to the bottom of the page to load all flyers
        last_height = driver.execute_script("return document.body.scrollHeight")

        while True:
            # Wait for flyers to load
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, f"a.{flyer_class}"))
            )

            # Get all flyer elements
            flyers = driver.find_elements(By.CSS_SELECTOR, f"a.{flyer_class}")

            # Extract links
            for flyer in flyers:
                href = flyer.get_attribute("href")
                if href not in flyer_links:
                    flyer_links.append(href)
                    print(f"Flyer URL: {href}")

            # Scroll down
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # Wait for new content to load
            WebDriverWait(driver, 5).until(
                lambda driver: driver.execute_script(
                    "return document.body.scrollHeight"
                )
                > last_height
            )

            # Update last height and check if we have reached the bottom of the page
            last_height = driver.execute_script("return document.body.scrollHeight")
            if (
                driver.execute_script("return window.innerHeight + window.scrollY")
                >= last_height
            ):
                break

    except Exception as e:
        print(f"Error fetching flyer links: {str(e)}")

    return flyer_links


def main():
    url = "https://flipp.com/en-ca/pierrefonds-qc/flyer/6684596-super-c-flyer?postal_code=H8Y3P2"
    driver = setup_chrome_driver()

    try:
        # soup = load_webpage_content(driver, url)
        # extract_item_infos(driver, soup)
        get_flyer_links(
            driver=driver,
            homepage_url="https://flipp.com/en-ca/pierrefonds-qc/flyers/groceries?postal_code=H8Y3P2",
        )
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
