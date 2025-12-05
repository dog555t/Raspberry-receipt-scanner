import re
import uuid
from datetime import datetime
from typing import Dict, Optional

import cv2
import numpy as np
import pytesseract
from PIL import Image

CURRENCY_REGEX = re.compile(r"([$€£]|USD|EUR|GBP)")
DATE_REGEX = re.compile(
    r"((?:\d{4}[/-]\d{2}[/-]\d{2})|(?:\d{2}[/-]\d{2}[/-]\d{4})|(?:\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}))"
)
TOTAL_REGEX = re.compile(r"(total|amount due|grand total)[:\s]*([\d.,]+)", re.IGNORECASE)
TAX_REGEX = re.compile(r"(tax|vat)[:\s]*([\d.,]+)", re.IGNORECASE)


def preprocess_image(image_path: str) -> Image.Image:
    image = cv2.imread(image_path)
    if image is None:
        return Image.open(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Attempt a simple deskew using moments
    coords = np.column_stack(np.where(thresh > 0))
    angle = cv2.minAreaRect(coords)[-1] if coords.size else 0
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    (h, w) = thresh.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(thresh, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return Image.fromarray(rotated)


def extract_amounts(text: str) -> Dict[str, Optional[float]]:
    total = None
    tax = None
    for match in TOTAL_REGEX.finditer(text):
        try:
            total = float(match.group(2).replace(",", ""))
        except ValueError:
            continue
    for match in TAX_REGEX.finditer(text):
        try:
            tax = float(match.group(2).replace(",", ""))
        except ValueError:
            continue
    if total is None:
        # fallback: pick largest number
        numbers = [float(x.replace(",", "")) for x in re.findall(r"[0-9]+\.[0-9]{2}", text)]
        if numbers:
            total = max(numbers)
    return {"total_amount": total, "tax_amount": tax}


def extract_date(text: str) -> Optional[str]:
    match = DATE_REGEX.search(text)
    if match:
        raw = match.group(0)
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%d %B %Y", "%d %b %Y"]:
            try:
                return datetime.strptime(raw, fmt).date().isoformat()
            except ValueError:
                continue
        return raw
    return None


def extract_vendor(lines) -> Optional[str]:
    if not lines:
        return None
    # Heuristic: first non-empty line that isn't a date or numeric
    for line in lines[:5]:
        if len(line.strip()) > 2 and not re.search(r"\d", line):
            return line.strip()
    return lines[0].strip()


def process_image(image_path: str) -> Dict[str, Optional[str]]:
    processed = preprocess_image(image_path)
    raw_text = pytesseract.image_to_string(processed)
    lines = [line for line in raw_text.splitlines() if line.strip()]

    amounts = extract_amounts(raw_text)
    date = extract_date(raw_text)
    vendor = extract_vendor(lines)

    currency_match = CURRENCY_REGEX.search(raw_text)
    currency = None
    if currency_match:
        symbol = currency_match.group(1)
        currency = {"$": "USD", "€": "EUR", "£": "GBP"}.get(symbol, symbol)

    return {
        "id": str(uuid.uuid4()),
        "date": date,
        "vendor": vendor,
        "total_amount": amounts.get("total_amount"),
        "tax_amount": amounts.get("tax_amount"),
        "currency": currency,
        "payment_method": None,
        "category": None,
        "notes": None,
        "image_path": image_path,
        "raw_text": raw_text,
    }
