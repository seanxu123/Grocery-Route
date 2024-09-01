from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Part
import requests
import io
from collections import deque
from datetime import timedelta, datetime
import time
import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
BUCKET_NAME = os.getenv("BUCKET_NAME")

storage_client = storage.Client(project=PROJECT_ID)

regions = ["us-central1", "us-east4", "us-west1", "us-west4", "northamerica-northeast1", "europe-west1", "europe-west2", "europe-west3",
           "europe-west4", "europe-west9", "asia-northeast1", "asia-northeast3", "asia-southeast1"]
region_call_limit = 5  # 5 calls per minute per region

# Tracking calls per region with timestamps
call_counters = {region: deque(maxlen=region_call_limit) for region in regions}
current_region_index = 0

def switch_region():
    global current_region_index
    current_region_index = (current_region_index + 1) % len(regions)
    print(f"Switching region from {regions[(current_region_index - 1) % len(regions)]} to {regions[current_region_index]}")
    return regions[current_region_index]


def can_make_call(region):
    """Check if we can make an API call in the specified region."""
    one_minute_ago = datetime.now() - timedelta(minutes=1)
    # Remove outdated timestamps (older than 1 minute)
    while call_counters[region] and call_counters[region][0] < one_minute_ago:
        call_counters[region].popleft()
    
    return len(call_counters[region]) < region_call_limit


def record_call(region):
    """Record an API call timestamp for the specified region."""
    call_counters[region].append(datetime.now())


def reset_call_counters():
    global call_counters
    call_counters = {region: 0 for region in regions}
    

def download_image(image_url):
    """Downloads an image from a URL."""
    response = requests.get(image_url, stream=True)
    if response.status_code == 200:
        image_stream = io.BytesIO(response.content)
        return image_stream


def create_blob(bucket_name, blob_name):
    """Creates a blob in the specified bucket."""
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob


def upload_to_gcs(blob, image_stream):
    """Uploads a file-like object to Google Cloud Storage."""
    blob.upload_from_file(image_stream, content_type='image/jpeg')
    return f"gs://{BUCKET_NAME}/{blob.name}"


def delete_from_gcs(blob):
    """Deletes a blob from Google Cloud Storage."""
    blob.delete()


def generate_response(image_url, prompt):
    """
    Uploads an image to Google Cloud Storage, processes it using Vertex AI,
    and deletes the image from GCS after processing.
    """
    global current_region_index
    
    while not can_make_call(regions[current_region_index]):
        print(f"Region {regions[current_region_index]} reached API call limit. Switching region...")
        switch_region()
        
    region = regions[current_region_index]
        
    try:        
        image_stream = download_image(image_url)
        blob_name = "temp_image.jpg"
        blob = create_blob(BUCKET_NAME, blob_name)
        
        gcs_uri = upload_to_gcs(blob, image_stream)
        
        vertexai.init(project=PROJECT_ID, location=region)
        model = GenerativeModel("gemini-1.5-flash-001")
        
        response = model.generate_content(
            [
                Part.from_uri(gcs_uri, mime_type="image/jpeg"),
                prompt,
            ]
        )
        
        record_call(region)
        print(f"API call count for {region} in the last minute: {len(call_counters[region])}")
        
        return response.text

    except Exception as e:
        print(f"An error occurred when processing image: {e}")
        return None

    finally:
        delete_from_gcs(blob)
        
        if all(not can_make_call(region) for region in regions):
            print("All regions reached limit. Waiting to reset counters...")
            time.sleep(60)  # Wait for 60 seconds before retrying
        


def is_valid_item(image_url):
    is_valid_prompt = "Is this a flyer item with a price. Seeing a percentage only doesn't count, you need to see a dollar amount. Answer yes or no in lowercase without punctuation"
    is_valid_item = generate_response(image_url, is_valid_prompt)
    print(f"Is valid item: {is_valid_item}")
    
    if is_valid_item.strip() == "yes":
        return True
    else:
        print("This is not a valid item")
        return False


def get_flyer_image_infos(image_url):
    if is_valid_item(image_url):
        prompt ="Tell me the name of the item in less than 5 words. What is the price of the item (no dollar sign, just a float)? "\
                "Directly tell me the answer, without saying the item is or the price is. "\
                "Tell me the quantity of the item by weight (#lbs, #kg), quantity (2 units, 3 units, ...), each, etc). Please put a space between number and symbols"\
                "Separate the answers with a comma."
        response = generate_response(image_url, prompt)
        item_name, price, unit = response.split(',')
        return item_name.strip(), price.strip(), unit.strip()
    else:
        return None, None, None

    
