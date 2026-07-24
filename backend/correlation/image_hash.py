from pathlib import Path

from PIL import Image


def average_hash(image_path: str, hash_size: int = 8) -> str:
    image = Image.open(Path(image_path)).convert("L").resize((hash_size, hash_size))
    pixels = list(image.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= avg else "0" for pixel in pixels)
    return f"{int(bits, 2):0{hash_size * hash_size // 4}x}"
