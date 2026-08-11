from models import BookRecord
import os
import json

def parse_price(price_text: str) -> float:
    """
    Parses the price text and returns the price as a float.
    """
    try:
        return float(price_text.replace("£", "").strip())
    except ValueError:
        raise ValueError(f"Could not parse price from: {price_text}")


def validate_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Validates the raw book records against the BookRecord model.
    """
    valid_records = []
    invalid_records = []
    seen = set()
    for record in records:
        try:
            price_gbp = parse_price(record["price_text"])
            book = BookRecord(**{**record, "price_gbp": price_gbp})
            url = str(book.product_url)
            if url in seen:
                invalid_records.append({"record": record, "error": "Duplicate URL"})
                continue

            seen.add(url)
            valid_records.append(book.model_dump(mode="json"))

        except Exception as e:
            invalid_records.append({"record": record, "error": str(e)})

    return valid_records, invalid_records


def write_output(valid_records: list[dict], invalid_records: list[dict]):
    """
    Writes the valid and invalid records to JSON files in the output directory.
    """
    os.makedirs("output", exist_ok=True)
    with open("output/books.json", "w", encoding = "utf-8") as f:
        json.dump(valid_records, f, indent=4)

    with open("output/errors.json", "w", encoding = "utf-8") as f:
            json.dump(invalid_records, f, indent=4)
