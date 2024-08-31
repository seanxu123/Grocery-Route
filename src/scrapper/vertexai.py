from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Part
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


def generate_response(image_stream, prompt):
    """
    Uploads an image to Google Cloud Storage, processes it using Vertex AI,
    and deletes the image from GCS after processing.
    """
    try:
        blob_name = "temp_image.jpg"
        blob = create_blob(BUCKET_NAME, blob_name)
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
    image_stream = download_image(image_url)
    response = generate_response(image_stream, prompt)
    item_name, price = response.split(',')
    return item_name.strip(), price.strip()

