import logging
import imagehash
from PIL import Image
from pathlib import Path
from typing import List, Dict, Any, Tuple
from app.config import BASE_DIR

logger = logging.getLogger(__name__)

def compute_perceptual_hash(image_path: str) -> Optional[str]:
    """Computes a 64-bit pHash perceptual image hash for identity profile picture matching (§7)."""
    full_path = BASE_DIR / "data" / image_path if not Path(image_path).is_absolute() else Path(image_path)
    if not full_path.exists():
        return None

    try:
        with Image.open(full_path) as img:
            phash = imagehash.phash(img)
            return str(phash)
    except Exception as e:
        logger.warning("Error computing imagehash for %s: %s", image_path, e)
        return None

def match_profile_pictures(hits: List[Dict[str, Any]], max_hamming_distance: int = 8) -> List[Tuple[int, int, int]]:
    """
    Compares perceptual hashes across all hits in an investigation.
    Returns list of tuples: (hit_id_1, hit_id_2, hamming_distance).
    Used to detect reused profile pictures (near-duplicate detector).
    """
    matches = []
    hashes = {}

    for hit in hits:
        hit_id = hit.get("id")
        pic = hit.get("profile_picture_path") or hit.get("avatar_url")
        if hit_id and pic:
            h = compute_perceptual_hash(pic)
            if h:
                hashes[hit_id] = imagehash.hex_to_hash(h)

    hit_ids = list(hashes.keys())
    for i in range(len(hit_ids)):
        for j in range(i + 1, len(hit_ids)):
            id1, id2 = hit_ids[i], hit_ids[j]
            dist = hashes[id1] - hashes[id2]
            if dist <= max_hamming_distance:
                matches.append((id1, id2, dist))

    return matches
