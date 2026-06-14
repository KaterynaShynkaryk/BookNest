import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GOOGLE_BOOKS_SEARCH_URL = "https://www.googleapis.com/books/v1/volumes"
OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
OPEN_LIBRARY_COVER_URL = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
OPEN_LIBRARY_WORK_URL = "https://openlibrary.org{key}"
USER_AGENT = "BookNest demo app (book search; contact: demo@booknest.local)"


class BookLookupError(Exception):
    pass


def search_books(query, limit=10):
    """Search Google Books first, then use Open Library as a best-effort fallback."""
    query = query.strip()
    if not query:
        return []

    return search_with_fallback(query, limit=limit)


def search_with_fallback(query, limit=10):
    providers = (search_google_books, search_open_library_books)

    for provider in providers:
        try:
            results = provider(query, limit=limit)
        except BookLookupError:
            continue
        if results:
            return results

    return []


def search_google_books(query, limit=10):
    return search_google_books_query(query, limit=limit)


def search_google_books_query(query, limit=10):
    params = urlencode(
        {
            "q": query,
            "maxResults": min(limit, 40),
            "printType": "books",
            "orderBy": "relevance",
        }
    )
    payload = fetch_json(f"{GOOGLE_BOOKS_SEARCH_URL}?{params}", "Google Books")
    return [normalize_google_books_item(item) for item in payload.get("items", [])]


def search_open_library_books(query, limit=10):
    params = urlencode(
        {
            "title": query,
            "limit": limit,
            "fields": "key,title,author_name,first_publish_year,publisher,subject,cover_i",
        }
    )
    payload = fetch_json(f"{OPEN_LIBRARY_SEARCH_URL}?{params}", "Open Library")
    return [normalize_open_library_doc(doc) for doc in payload.get("docs", [])]


def fetch_json(url, provider_name):
    request = Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise BookLookupError(f"Не вдалося отримати дані з {provider_name}.") from exc


def normalize_google_books_item(item):
    volume = item.get("volumeInfo", {})
    image_links = volume.get("imageLinks", {})
    cover_url = image_links.get("thumbnail") or image_links.get("smallThumbnail") or ""
    if cover_url.startswith("http://"):
        cover_url = "https://" + cover_url.removeprefix("http://")

    return {
        "title": volume.get("title", "").strip(),
        "author": ", ".join(volume.get("authors", [])[:3]),
        "published_year": parse_published_year(volume.get("publishedDate", "")),
        "publisher": volume.get("publisher", ""),
        "genre": ", ".join(volume.get("categories", [])[:3]),
        "cover_url": cover_url,
        "external_id": item.get("id", ""),
        "external_url": volume.get("infoLink") or volume.get("previewLink") or "",
        "source": "Google Books",
    }


def normalize_open_library_doc(doc):
    authors = doc.get("author_name") or []
    publishers = doc.get("publisher") or []
    subjects = doc.get("subject") or []
    cover_id = doc.get("cover_i")
    key = doc.get("key", "")

    return {
        "title": doc.get("title", "").strip(),
        "author": ", ".join(authors[:3]),
        "published_year": doc.get("first_publish_year") or "",
        "publisher": publishers[0] if publishers else "",
        "genre": ", ".join(subjects[:3]),
        "cover_url": OPEN_LIBRARY_COVER_URL.format(cover_id=cover_id) if cover_id else "",
        "external_id": key,
        "external_url": OPEN_LIBRARY_WORK_URL.format(key=key) if key else "",
        "source": "Open Library",
    }


def parse_published_year(published_date):
    if not published_date:
        return ""

    import re

    match = re.search(r"\d{4}", str(published_date))
    return match.group(0) if match else ""

BOOK_URL_ALLOWED_SCHEMES = ("http://", "https://")


def import_book_from_url(url):
    url = url.strip()
    if not url.startswith(BOOK_URL_ALLOWED_SCHEMES):
        return []

    payload = fetch_text(url, "сторінки книги")
    metadata = extract_book_metadata(payload)
    if not metadata.get("title"):
        return []

    metadata.setdefault("external_url", url)
    metadata.setdefault("source", "Сторінка книги")
    return [metadata]


def fetch_text(url, provider_name):
    request = Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urlopen(request, timeout=8) as response:
            content_type = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(content_type, errors="replace")
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError) as exc:
        raise BookLookupError(f"Не вдалося отримати дані з {provider_name}.") from exc


def extract_book_metadata(html):
    for json_ld in extract_json_ld_blocks(html):
        metadata = metadata_from_json_ld(json_ld)
        if metadata.get("title"):
            return enrich_metadata_from_html(metadata, html)

    return enrich_metadata_from_html(metadata_from_open_graph(html), html)


def extract_json_ld_blocks(html):
    import re

    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    blocks = []
    for match in pattern.finditer(html):
        raw_json = unescape_html(match.group(1).strip())
        try:
            blocks.append(json.loads(raw_json))
        except json.JSONDecodeError:
            continue
    return blocks


def metadata_from_json_ld(data):
    if isinstance(data, list):
        for item in data:
            metadata = metadata_from_json_ld(item)
            if metadata.get("title"):
                return metadata
        return {}

    if not isinstance(data, dict):
        return {}

    graph = data.get("@graph")
    if graph:
        metadata = metadata_from_json_ld(graph)
        if metadata.get("title"):
            return metadata

    item_type = data.get("@type", "")
    item_types = item_type if isinstance(item_type, list) else [item_type]
    if not any(str(value).lower() in {"book", "product"} for value in item_types):
        return {}

    author = data.get("author") or ""
    if isinstance(author, list):
        author = ", ".join(filter(None, [extract_name(value) for value in author[:3]]))
    else:
        author = extract_name(author)

    image = data.get("image") or ""
    if isinstance(image, list):
        image = image[0] if image else ""
    elif isinstance(image, dict):
        image = image.get("url", "")

    publisher = extract_name(data.get("publisher", ""))
    properties = extract_additional_properties(data)
    author = author or find_property_value(properties, ["автор", "авторка", "автори", "author"])
    publisher = publisher or find_property_value(properties, ["видавництво", "видавець", "publisher"])
    published_year = parse_published_year(str(data.get("datePublished", ""))) or parse_published_year(
        find_property_value(properties, ["рік видання", "дата видання", "publication date", "published"])
    )

    return {
        "title": str(data.get("name") or data.get("headline") or "").strip(),
        "author": author,
        "published_year": published_year,
        "publisher": publisher,
        "genre": "",
        "cover_url": str(image),
        "description": strip_tags(str(data.get("description") or "")),
        "external_id": str(data.get("isbn") or data.get("sku") or find_property_value(properties, ["isbn"]) or ""),
        "external_url": str(data.get("url") or ""),
        "source": "Сторінка книги",
    }


def metadata_from_open_graph(html):
    title = extract_meta_content(html, "property", "og:title") or extract_title(html)
    description = extract_meta_content(html, "property", "og:description")
    image = extract_meta_content(html, "property", "og:image")
    url = extract_meta_content(html, "property", "og:url")

    return {
        "title": strip_title_suffix(title),
        "author": extract_meta_content(html, "name", "author") or extract_meta_content(html, "property", "book:author"),
        "published_year": parse_published_year(
            extract_meta_content(html, "property", "book:release_date")
            or extract_meta_content(html, "property", "article:published_time")
        ),
        "publisher": extract_meta_content(html, "property", "book:publisher"),
        "genre": "",
        "cover_url": image,
        "description": strip_tags(description),
        "external_id": "",
        "external_url": url,
        "source": "Сторінка книги",
    }



def extract_additional_properties(data):
    properties = {}
    raw_properties = data.get("additionalProperty") or data.get("additionalProperties") or []
    if isinstance(raw_properties, dict):
        raw_properties = [raw_properties]

    for item in raw_properties:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("propertyID") or "").strip().casefold()
        value = item.get("value") or item.get("description") or ""
        if name and value:
            properties[name] = strip_tags(str(value))

    return properties


def find_property_value(properties, labels):
    for label in labels:
        label = label.casefold()
        for key, value in properties.items():
            if label in key and value:
                return value
    return ""


def enrich_metadata_from_html(metadata, html):
    metadata = dict(metadata)
    metadata["author"] = metadata.get("author") or extract_labeled_value(
        html, ["Автор", "Авторка", "Автори", "Author"]
    )
    metadata["publisher"] = metadata.get("publisher") or extract_labeled_value(
        html, ["Видавництво", "Видавець", "Publisher"]
    )
    metadata["published_year"] = metadata.get("published_year") or parse_published_year(
        extract_labeled_value(html, ["Рік видання", "Дата видання", "Publication year", "Published"])
    )
    return metadata


def extract_labeled_value(html, labels):
    import re

    visible_html = remove_non_content_tags(html)
    for label in labels:
        structured_patterns = (
            rf"<(?:dt|th)[^>]*>\s*{re.escape(label)}\s*</(?:dt|th)>\s*<(?:dd|td)[^>]*>(.*?)</(?:dd|td)>",
            rf"<(?:span|div|p|li)[^>]*>\s*{re.escape(label)}\s*</(?:span|div|p|li)>\s*<(?:span|div|p)[^>]*>(.*?)</(?:span|div|p)>",
        )
        for pattern in structured_patterns:
            match = re.search(pattern, visible_html, re.IGNORECASE | re.DOTALL)
            if match:
                value = clean_labeled_value(match.group(1))
                if value:
                    return value

    text = strip_tags(visible_html)
    stop_labels = (
        "Автор", "Авторка", "Автори", "Видавництво", "Видавець", "Рік видання",
        "Дата видання", "ISBN", "Жанр", "Кількість сторінок", "Палітурка",
        "Author", "Publisher", "Publication year", "Published", "Language", "Pages",
    )
    stop_pattern = "|".join(re.escape(label) for label in stop_labels)

    for label in labels:
        pattern = re.compile(
            rf"{re.escape(label)}\s*[:—-]\s*(.+?)(?=\s+(?:{stop_pattern})\s*[:—-]|$)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            value = clean_labeled_value(match.group(1))
            if value:
                return value
    return ""


def remove_non_content_tags(html):
    import re

    return re.sub(
        r"<(script|style|noscript|svg)[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )


def clean_labeled_value(value):
    value = strip_tags(value).strip(" :—-")[:160].strip()
    if not value or len(value) < 2:
        return ""

    lowered = value.casefold()
    rejected_fragments = (
        "купити", "доставка", "кошик", "сайт", "сторінка", "каталог", "пошук",
        "booknest", "yakaboo", "readeat", "google", "open library",
    )
    if any(fragment in lowered for fragment in rejected_fragments):
        return ""

    return value


def extract_name(value):
    if isinstance(value, dict):
        return str(value.get("name", "")).strip()
    return str(value).strip()


def extract_meta_content(html, attribute, value):
    import re

    meta_pattern = re.compile(r"<meta[^>]*>", re.IGNORECASE | re.DOTALL)
    attribute_pattern = re.compile(
        rf'{attribute}=["\']{re.escape(value)}["\']',
        re.IGNORECASE,
    )
    content_pattern = re.compile(r'content=["\'](.*?)["\']', re.IGNORECASE | re.DOTALL)

    for tag in meta_pattern.findall(html):
        if not attribute_pattern.search(tag):
            continue
        match = content_pattern.search(tag)
        if match:
            return unescape_html(match.group(1).strip())
    return ""


def extract_title(html):
    import re

    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return unescape_html(match.group(1).strip()) if match else ""


def strip_title_suffix(title):
    return title.split(" | ", 1)[0].split(" - ", 1)[0].strip()


def strip_tags(value):
    import re

    text = re.sub(r"<[^>]+>", " ", unescape_html(value))
    return re.sub(r"\s+", " ", text).strip()


def unescape_html(value):
    from html import unescape

    return unescape(value)