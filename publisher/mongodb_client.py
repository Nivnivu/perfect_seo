"""Direct MongoDB client for inserting blog posts into the pawly collection."""
from datetime import datetime, timezone


def _get_client(config):
    from pymongo import MongoClient
    return MongoClient(config["mongodb"]["uri"])


def get_master_user_id(config):
    """
    Query usersCollection for a user with role: "master".
    Works for all blogs/collections.
    Returns the user's _id as a string, or None if not found.
    """
    client = _get_client(config)
    db = client[config["mongodb"]["database"]]
    users = db["usersCollection"]

    user = users.find_one({"role": "master"})

    client.close()

    if user:
        return str(user["_id"])

    return None


def insert_blog_post(post_data, config):
    """
    Insert a blog post document into the pawly collection.
    post_data should contain: title, subtitle, body (TipTap JSON string),
    image1Url, image2Url, userId
    Returns the inserted document _id as string.
    """
    client = _get_client(config)
    db = client[config["mongodb"]["database"]]
    collection = db[config["mongodb"]["collection"]]

    document = {
        "userId": post_data["userId"],
        "title": post_data["title"],
        "subtitle": post_data["subtitle"],
        "body": post_data["body"],
        "blog": config["mongodb"]["collection"],
        "image1Url": post_data["image1Url"],
        "image2Url": post_data["image2Url"],
        "createdAt": datetime.now(timezone.utc),
        "type": "blogPost",
    }

    result = collection.insert_one(document)
    client.close()

    return str(result.inserted_id)


def update_blog_post(post_id, update_fields, config):
    """
    Update specific fields of a blog post by its _id.
    update_fields: dict of fields to update, e.g. {"image1Url": "xxx.jpg", "title": "new title"}
    """
    from bson import ObjectId
    client = _get_client(config)
    db = client[config["mongodb"]["database"]]
    collection = db[config["mongodb"]["collection"]]

    result = collection.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": update_fields},
    )
    client.close()
    return result.modified_count


def _post_to_dict(post):
    """Convert a MongoDB post document to a standard dict."""
    return {
        "_id": str(post["_id"]),
        "title": post.get("title", ""),
        "image1Url": post.get("image1Url", ""),
        "image2Url": post.get("image2Url", ""),
    }


def _normalize_words(text):
    """Lowercase, strip punctuation, split into a set of words."""
    import re
    text = text.lower()
    # Replace hyphens and common punctuation with spaces
    text = re.sub(r'[-_:;,.|!?()\'\"–—/\\]', ' ', text)
    return set(w for w in text.split() if len(w) > 1)


def find_post_by_title(title_fragment, config):
    """
    Find a post in the pawly collection by partial title match.
    Strips common site name suffixes (e.g. " | מכללת אוורסט") before searching.
    Returns dict with _id, title, image1Url, image2Url (or None if not found).
    """
    import re
    client = _get_client(config)
    db = client[config["mongodb"]["database"]]
    collection = db[config["mongodb"]["collection"]]

    # Strip site name suffixes: "Title | Site", "Title - Site", "Title – Site", "Title — Site"
    clean_title = re.split(r'\s*[|–—]\s*|\s+-\s+', title_fragment)[0].strip()
    escaped = re.escape(clean_title[:50])

    post = collection.find_one(
        {"title": {"$regex": escaped, "$options": "i"}},
        {"title": 1, "image1Url": 1, "image2Url": 1},
    )
    client.close()

    if post:
        return _post_to_dict(post)
    return None


def find_post_by_url(url, config):
    """
    Fallback: extract the slug from the post URL, fetch all blogPosts,
    and find the best match by word overlap between slug and title.
    Returns dict with _id, title, image1Url, image2Url (or None).
    """
    from urllib.parse import unquote
    if not url:
        return None

    # Extract slug from URL path  (last segment)
    slug = unquote(url.rstrip("/").split("/")[-1])
    slug_words = _normalize_words(slug)
    if not slug_words:
        return None

    client = _get_client(config)
    db = client[config["mongodb"]["database"]]
    collection = db[config["mongodb"]["collection"]]

    all_posts = list(collection.find(
        {"type": "blogPost"},
        {"title": 1, "image1Url": 1, "image2Url": 1},
    ))
    client.close()

    best_post = None
    best_score = 0

    for post in all_posts:
        title = post.get("title", "")
        title_words = _normalize_words(title)
        if not title_words:
            continue
        # Jaccard-like: intersection over the smaller set
        overlap = len(slug_words & title_words)
        score = overlap / min(len(slug_words), len(title_words))
        if score > best_score:
            best_score = score
            best_post = post

    # Require at least 50% word overlap to consider it a match
    if best_post and best_score >= 0.5:
        return _post_to_dict(best_post)
    return None


def fetch_all_blog_posts(config):
    """Fetch all blogPost documents from MongoDB (with body for content analysis)."""
    client = _get_client(config)
    db = client[config["mongodb"]["database"]]
    collection = db[config["mongodb"]["collection"]]

    posts = list(collection.find(
        {"type": "blogPost"},
        {"title": 1, "subtitle": 1, "body": 1, "image1Url": 1, "image2Url": 1},
    ))
    client.close()

    for p in posts:
        p["_id"] = str(p["_id"])
    return posts


def fetch_posts_missing_images(config):
    """Fetch all blogPost documents where image1Url or image2Url is empty/missing."""
    client = _get_client(config)
    db = client[config["mongodb"]["database"]]
    collection = db[config["mongodb"]["collection"]]

    posts = list(collection.find({
        "type": "blogPost",
        "$or": [
            {"image1Url": {"$in": ["", None]}},
            {"image1Url": {"$exists": False}},
            {"image2Url": {"$in": ["", None]}},
            {"image2Url": {"$exists": False}},
        ]
    }, {"title": 1, "image1Url": 1, "image2Url": 1}))
    client.close()

    for p in posts:
        p["_id"] = str(p["_id"])
    return posts


def fetch_recent_posts(config, limit=5):
    """Fetch recent blog posts from the pawly collection (for context/debugging)."""
    client = _get_client(config)
    db = client[config["mongodb"]["database"]]
    collection = db[config["mongodb"]["collection"]]

    posts = list(collection.find().sort("createdAt", -1).limit(limit))
    client.close()

    # Convert ObjectId to string for printing
    for post in posts:
        post["_id"] = str(post["_id"])

    return posts


def fetch_static_pages(config):
    """Fetch all staticPage documents from the collection."""
    client = _get_client(config)
    db = client[config["mongodb"]["database"]]
    collection = db[config["mongodb"]["collection"]]

    pages = list(collection.find({"type": "staticPage"}))
    client.close()

    for page in pages:
        page["_id"] = str(page["_id"])

    return pages


def update_static_page(page_id, title, content, config):
    """
    Update a static page's title and content by its _id.
    content: TipTap JSON object (dict, not string).
    """
    from bson import ObjectId
    client = _get_client(config)
    db = client[config["mongodb"]["database"]]
    collection = db[config["mongodb"]["collection"]]

    result = collection.update_one(
        {"_id": ObjectId(page_id)},
        {"$set": {
            "title": title,
            "content": content,
            "updatedAt": datetime.now(timezone.utc),
        }},
    )
    client.close()
    return result.modified_count
