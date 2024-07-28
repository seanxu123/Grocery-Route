import cv2
import pytesseract
from PIL import Image
import re

# Load the image using OpenCV
image = cv2.imread("test_image.jpg")

# Resize the image to improve OCR accuracy
image = cv2.resize(image, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

# Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization) for each channel
lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
l, a, b = cv2.split(lab)
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
l = clahe.apply(l)
lab = cv2.merge((l, a, b))
enhanced_image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

# Apply Gaussian blur to reduce noise
blurred = cv2.GaussianBlur(enhanced_image, (5, 5), 0)

# Save the preprocessed image (optional)
cv2.imwrite("preprocessed_image.jpg", blurred)

# Use Tesseract to extract text
text = pytesseract.image_to_string(blurred)

print(f"Extracted Text: {text}")

# Use regular expression to find all numbers
numbers = re.findall(r"\d+", text)
print(f"Extracted Numbers: {numbers}")

# Find specific keywords (optional)
keywords = ["price", "cost", "amount"]
for keyword in keywords:
    if keyword in text.lower():
        print(f"Keyword '{keyword}' found in text.")
