"""
One-time migration: copy 3 product updates from multiBlogDB → pawly.
These products were written to the wrong DB before the fix.
"""
import yaml
from bson import ObjectId
from pymongo import MongoClient

PRODUCT_IDS = [
    "686f7adffca5fb429f2cc32b",
    "686f7adffca5fb429f2cc32c",
    "686f7adffca5fb429f2cc32d",
]

FIELDS_TO_COPY = ["content", "metaDescription", "mediaUrl"]


def load_config(path="config.pawly.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_media_url(media_url, config, users_col):
    """If mediaUrl is a bare filename (pre-fix), build the full Supabase public URL."""
    if not media_url or media_url.startswith("http"):
        return media_url  # already full URL or empty

    # Bare filename — reconstruct full URL using master user ID
    user = users_col.find_one({"role": "master"})
    user_id = str(user["_id"]) if user else None
    if not user_id:
        print("  [WARN] Could not find master user — mediaUrl left as-is")
        return media_url

    supabase_url = config["supabase"]["url"].rstrip("/")
    bucket = config["supabase"]["bucket"]
    full_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{user_id}/{media_url}"
    print(f"  [mediaUrl] {media_url} -> {full_url}")
    return full_url


def main():
    config = load_config()
    uri = config["mongodb"]["uri"]

    client = MongoClient(uri)

    src_col = client["multiBlogDB"]["wordpress_products"]
    dst_col = client["pawly"]["wordpress_products"]
    users_col = client[config["mongodb"]["database"]]["usersCollection"]

    for pid in PRODUCT_IDS:
        oid = ObjectId(pid)
        src_doc = src_col.find_one({"_id": oid})
        if not src_doc:
            print(f"  [MISS] {pid} not found in multiBlogDB")
            continue

        update_fields = {k: src_doc[k] for k in FIELDS_TO_COPY if k in src_doc}
        if not update_fields:
            print(f"  [SKIP] {pid} — no relevant fields found")
            continue

        # Fix mediaUrl if it's a bare filename
        if "mediaUrl" in update_fields:
            update_fields["mediaUrl"] = _resolve_media_url(
                update_fields["mediaUrl"], config, users_col
            )

        result = dst_col.update_one({"_id": oid}, {"$set": update_fields})
        if result.matched_count:
            print(f"  [OK]   {pid} — copied: {list(update_fields.keys())}")
        else:
            print(f"  [MISS] {pid} not found in pawly DB")

    client.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
