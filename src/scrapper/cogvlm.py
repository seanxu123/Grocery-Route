import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import os
import re
import warnings

warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Load the model and tokenizer
MODEL_PATH = "THUDM/cogvlm2-llama3-chat-19B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
TORCH_TYPE = (
    torch.bfloat16
    if torch.cuda.is_available() and torch.cuda.get_device_capability()[0] >= 8
    else torch.float16
)
DESCRIPTION_LENGTH_LIMIT = 500
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)


def generate_cogvlm_model() -> None:
    """
    Generates and returns the CogVLM model.

    Returns:
    - AutoModelForCausalLM: The loaded CogVLM model.
    """
    cogvlm_model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        torch_dtype=TORCH_TYPE,
        trust_remote_code=True,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True),
        low_cpu_mem_usage=True,
    ).eval()
    return cogvlm_model


def generate_response(
    model,
    query: str,
    image: Image
) -> str:
    """
    Generates a response using the model based on the given query and image.

    Args:
    - model (AutoModelForCausalLM): The model to generate the response.
    - query (str): The query string.
    - image (Image): The input image.

    Returns:
    - str: The generated response.
    """
    history = []

    if image is None:
        input_by_model = model.build_conversation_input_ids(
            tokenizer, query=query, history=history, template_version="chat"
        )
    else:
        input_by_model = model.build_conversation_input_ids(
            tokenizer,
            query=query,
            history=history,
            images=[image],
            template_version="chat",
        )

    inputs = {
        "input_ids": input_by_model["input_ids"].unsqueeze(0).to(DEVICE),
        "token_type_ids": input_by_model["token_type_ids"].unsqueeze(0).to(DEVICE),
        "attention_mask": input_by_model["attention_mask"].unsqueeze(0).to(DEVICE),
        "images": (
            [[input_by_model["images"][0].to(DEVICE).to(TORCH_TYPE)]]
            if image is not None
            else None
        ),
    }

    gen_kwargs = {
        "max_new_tokens": 512,
        "pad_token_id": 128002,
    }

    with torch.no_grad():
        outputs = model.generate(**inputs, **gen_kwargs)
        outputs = outputs[:, inputs["input_ids"].shape[1]:]
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)

    return response


def is_valid_item(model, image):
    price_label_prompt = "Do you see the item's price. Answer in one word with yes or no"
    has_price_label = generate_response(model, price_label_prompt, image)
    has_price_label = ''.join(char for char in has_price_label if char.isalpha())
    has_price_label = has_price_label.strip().lower()
    
    print(f"Has price label: {has_price_label}")
    
    if has_price_label == "no":
        return False
    else:
        return True
    

def clean_price_string(price_text):
    match = re.search(r'\$([\d.]+)', price_text)
    if match:
        price = match.group(1)
        return price
    return price_text


def generate_name_and_price(model, image):
    name_prompt = "What is this item in English? ANSWER IN LESS THAN 5 WORDS."
    price_prompt = "What is the price of the item in dollars? Answer in this format ($$.¢¢)"
    
    name = generate_response(model, name_prompt, image)
    price_text = generate_response(model, price_prompt, image)
    price = clean_price_string(price_text)
    return name, price
    

if __name__ == "__main__":
    model = generate_cogvlm_model()
    image_paths = ["test_image.jpg", "test_image_2.jpg", "test_image_3.jpg"]
    
    for image_path in image_paths:
        image = Image.open(image_path)
        price_label_prompt = "Do you see the item's price on the image. Answer in one word with yes or no without a period"
        has_price_label = generate_response(model, price_label_prompt, image)
        print(f"{image_path} is a valid item: {has_price_label}")