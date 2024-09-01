from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Part
import os
import requests
import io

PROJECT_ID = "spherical-berm-434101-k2"
BUCKET_NAME = "grocery-route"

storage_client = storage.Client(project=PROJECT_ID)

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
    try:
        blob_name = "temp_image.jpg"
        blob = create_blob(BUCKET_NAME, blob_name)
        image_stream = download_image(image_url)
        
        gcs_uri = upload_to_gcs(blob, image_stream)
        
        vertexai.init(project=PROJECT_ID, location="us-central1")
        model = GenerativeModel("gemini-1.5-flash-001")
        
        response = model.generate_content(
            [
                Part.from_uri(gcs_uri, mime_type="image/jpeg"),
                prompt,
            ]
        )
        return response.text

    except Exception as e:
        print(f"An error occurred when processing image: {e}")
        return None

    finally:
        delete_from_gcs(blob)


def get_item_name_and_price(image_url, prompt):
    response = generate_response(image_url, prompt)
    item_name, price = response.split(',')
    return item_name.strip(), price.strip()


def is_flyer_item(image_url, prompt):
    is_item = generate_response(image_url, prompt)
    return is_item


if __name__ == '__main__':
    #image_url = "https://f.wishabi.net/page_items/348585475/1724923926/extra_large.jpg" #rice
    image_url = "https://f.wishabi.net/page_items/348585476/1724923927/extra_large.jpg" #vermicelli
    #image_url = "https://f.wishabi.net/page_items/348585477/1724923928/extra_large.jpg" #honey
    
    #image_url = "https://f.wishabi.net/page_items/347689291/1724687488/extra_large.jpg" #walmart banner
    #image_url = "https://f.wishabi.net/page_pdf_images/19175647/80dc6dba-655b-11ef-bb3f-0edc53c25ee6/x_large" #Keurig banner
    #image_url = "https://f.wishabi.net/page_items/346370785/1723519477/extra_large.jpg" # La Moisson banner
    
    prompt = "Is this a flyer item with a price. Answer yes or no in lowercase without punctuation"
    
    is_item = is_flyer_item(image_url, prompt)
    print(f'Is flyer item: {is_item}')
    
