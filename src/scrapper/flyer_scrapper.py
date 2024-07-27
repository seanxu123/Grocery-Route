import requests
from bs4 import BeautifulSoup


def fetch_flyer(url):
    try:
        # Fetch the webpage
        response = requests.get(url)
        response.raise_for_status()  # Check for request errors
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching the flyer: {e}")
        return None


def parse_flyer(html):
    soup = BeautifulSoup(html, "html.parser")

    print(f"Soup: {soup}")

    items = []

    # Example: Modify these selectors based on actual flyer structure
    for item in soup.select(
        ".item-container"
    ):  # Replace '.item-class' with the actual class or selector
        name = item.select_one(".item-name-class").get_text(
            strip=True
        )  # Modify selector as needed
        price = item.select_one(".item-price-class").get_text(
            strip=True
        )  # Modify selector as needed
        details = {"name": name, "price": price}
        items.append(details)

    return items


def main():
    flyer_url = "https://flipp.com/en-ca/pierrefonds-qc/flyer/6684596-super-c-flyer?postal_code=H8Y3P2"  # Replace with actual flyer URL
    html = fetch_flyer(flyer_url)
    # print(f"html content: {html}")

    if html:
        items = parse_flyer(html)
        for item in items:
            print(f"Item: {item['name']}, Price: {item['price']}")
    else:
        print("Failed to fetch or parse flyer.")


if __name__ == "__main__":
    print("Executing scrapper ...")
    main()
