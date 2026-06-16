import json
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlencode
from urllib.request import Request, urlopen

GOOGLE_BOOKS_SEARCH_URL = "https://www.googleapis.com/books/v1/volumes"
OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
OPEN_LIBRARY_COVER_URL = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
OPEN_LIBRARY_WORK_URL = "https://openlibrary.org{key}"
USER_AGENT = "BookNest demo app (book search; contact: demo@booknest.local)"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
BOOK_PAGE_HEADERS = {
    "User-Agent": BROWSER_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
}
_TEXT_CACHE = {}


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
    results = []

    for provider in providers:
        try:
            results.extend(provider(query, limit=limit))
        except BookLookupError:
            continue

    return unique_book_results(results, limit=limit)


def search_google_books(query, limit=10):
    return collect_lookup_results(
        (query, f"intitle:{query}"),
        search_google_books_query,
        limit=limit,
    )


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
    return collect_lookup_results(
        (("title", query), ("q", query)),
        search_open_library_books_query,
        limit=limit,
    )


def search_open_library_books_query(query_filter, limit=10):
    field, query = query_filter
    params = urlencode(
        {
            field: query,
            "limit": limit,
            "fields": "key,title,author_name,first_publish_year,publisher,subject,cover_i",
        }
    )
    payload = fetch_json(f"{OPEN_LIBRARY_SEARCH_URL}?{params}", "Open Library")
    return [normalize_open_library_doc(doc) for doc in payload.get("docs", [])]


def collect_lookup_results(queries, lookup_func, limit=10):
    results = []
    had_success = False

    for query in queries:
        try:
            results.extend(lookup_func(query, limit=limit))
            had_success = True
        except BookLookupError:
            continue

    if not had_success:
        raise BookLookupError("Не вдалося отримати дані з каталогу книг.")

    return unique_book_results(results, limit=limit)


def unique_book_results(results, limit=10):
    unique_results = []
    seen = set()

    for result in results:
        title = str(result.get("title", "")).strip()
        if not title:
            continue

        key = (
            title.casefold(),
            str(result.get("author", "")).casefold(),
            str(result.get("published_year", "")),
        )
        if key in seen:
            continue

        seen.add(key)
        unique_results.append(result)
        if len(unique_results) >= limit:
            break

    return unique_results


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
    metadata = extract_book_metadata(payload, base_url=url) or {}
    if not metadata.get("title"):
        return []

    metadata.setdefault("external_url", url)
    metadata.setdefault("source", "Сторінка книги")
    return [metadata]


def fetch_text(url, provider_name):
    if url in _TEXT_CACHE:
        return _TEXT_CACHE[url]

    request = Request(url, headers=BOOK_PAGE_HEADERS)

    try:
        with urlopen(request, timeout=12) as response:
            content_type = response.headers.get_content_charset() or "utf-8"
            payload = response.read().decode(content_type, errors="replace")
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError) as exc:
        raise BookLookupError(f"Не вдалося отримати дані з {provider_name}.") from exc

    if not payload.strip():
        raise BookLookupError(f"Не вдалося отримати дані з {provider_name}.")

    _TEXT_CACHE[url] = payload
    return payload


def extract_book_metadata(html, base_url=""):
    for json_ld in extract_json_ld_blocks(html):
        metadata = metadata_from_json_ld(json_ld)
        if metadata.get("title"):
            return finalize_metadata(enrich_metadata_from_html(metadata, html), base_url=base_url)

    embedded_metadata = metadata_from_embedded_json(html)
    if embedded_metadata.get("title"):
        return finalize_metadata(enrich_metadata_from_html(embedded_metadata, html), base_url=base_url)

    open_graph_metadata = metadata_from_open_graph(html)
    if open_graph_metadata.get("title"):
        return finalize_metadata(enrich_metadata_from_html(open_graph_metadata, html), base_url=base_url)

    return {}

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


def metadata_from_embedded_json(html):
    for json_block in extract_json_script_blocks(html):
        metadata = metadata_from_json_tree(json_block)
        if metadata.get("title"):
            return metadata
    return {}


def extract_json_script_blocks(html):
    import re

    pattern = re.compile(
        r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>',
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


def metadata_from_json_tree(data):
    best_candidate = {}

    def walk(value):
        nonlocal best_candidate

        if isinstance(value, dict):
            candidate = metadata_from_flexible_dict(value)
            if candidate.get("title") and metadata_score(candidate) > metadata_score(best_candidate):
                best_candidate = candidate
            for nested_value in value.values():
                walk(nested_value)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(data)
    return best_candidate


def metadata_score(metadata):
    fields = ("title", "author", "publisher", "published_year", "genre", "cover_url", "description")
    return sum(1 for field in fields if metadata.get(field))


def metadata_from_flexible_dict(data):
    attributes = extract_attribute_values(data)

    title = first_value(data, ("title", "name", "productName", "displayName"))
    author = first_value(data, ("author", "authors", "authorName", "authorFullName"))
    publisher = first_value(
        data,
        (
            "publisher",
            "publisherName",
            "publisher_name",
            "publishingHouse",
            "publishing_house",
            "manufacturer",
        ),
    )
    published_year = parse_published_year(
        first_value(
            data,
            (
                "publishedYear",
                "publicationYear",
                "publication_year",
                "publishYear",
                "yearPublished",
                "year",
                "datePublished",
                "published_at",
            ),
        )
    )
    genre = first_value(data, ("genre", "category", "categoryName", "categories"))
    image = first_value(data, ("image", "images", "imageUrl", "cover", "coverUrl", "thumbnail"))
    description = first_value(data, ("description", "shortDescription", "annotation"))
    external_id = first_value(data, ("isbn", "sku", "code", "id"))
    external_url = first_value(data, ("url", "href", "canonical"))

    author = author or find_property_value(attributes, AUTHOR_LABELS)
    publisher = publisher or find_property_value(attributes, PUBLISHER_LABELS)
    published_year = published_year or parse_published_year(find_property_value(attributes, PUBLISHED_YEAR_LABELS))
    genre = genre or find_property_value(attributes, GENRE_LABELS)
    external_id = external_id or find_property_value(attributes, ["isbn"])

    return {
        "title": strip_title_suffix(clean_json_value(title)),
        "author": clean_labeled_value(clean_json_value(author)),
        "published_year": published_year,
        "publisher": clean_labeled_value(clean_json_value(publisher)),
        "genre": clean_labeled_value(clean_json_value(genre)),
        "cover_url": clean_json_value(image),
        "description": strip_tags(clean_json_value(description)),
        "external_id": clean_json_value(external_id),
        "external_url": clean_json_value(external_url),
        "source": "Сторінка книги",
    }


def first_value(data, keys):
    for key in keys:
        if key not in data:
            continue
        value = normalize_json_value(data.get(key))
        if value:
            return value
    return ""


def normalize_json_value(value):
    if isinstance(value, dict):
        for key in ("name", "title", "value", "url", "src", "href"):
            nested = normalize_json_value(value.get(key))
            if nested:
                return nested
        return ""
    if isinstance(value, list):
        values = [normalize_json_value(item) for item in value[:3]]
        return ", ".join(item for item in values if item)
    return str(value).strip() if value is not None else ""


def clean_json_value(value):
    return strip_tags(str(value or "")).strip()


def extract_attribute_values(data):
    attributes = {}
    attribute_sources = (
        data.get("attributes"),
        data.get("characteristics"),
        data.get("properties"),
        data.get("additionalProperty"),
        data.get("additionalProperties"),
    )

    for raw_attributes in attribute_sources:
        if isinstance(raw_attributes, dict):
            for key, value in raw_attributes.items():
                normalized_value = normalize_json_value(value)
                if key and normalized_value:
                    attributes[str(key).strip().casefold()] = clean_json_value(normalized_value)
        elif isinstance(raw_attributes, list):
            for item in raw_attributes:
                if not isinstance(item, dict):
                    continue
                name = str(
                    item.get("name")
                    or item.get("label")
                    or item.get("frontend_label")
                    or item.get("attribute_label")
                    or item.get("title")
                    or item.get("propertyID")
                    or item.get("attribute_code")
                    or item.get("code")
                    or item.get("key")
                    or ""
                ).strip().casefold()
                value = normalize_json_value(
                    item.get("value")
                    or item.get("values")
                    or item.get("description")
                    or item.get("text")
                    or item.get("option")
                    or item.get("display_value")
                )
                if name and value:
                    attributes[name] = clean_json_value(value)
    return attributes


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


AUTHOR_LABELS = ["Автор", "Авторка", "Автори", "Автор(и)", "Автор/ка", "Author"]
PUBLISHER_LABELS = ["Видавництво", "Видавець", "Publisher"]
PUBLISHED_YEAR_LABELS = [
    "Рік видання",
    "Дата видання",
    "Рік випуску",
    "Рік",
    "Publication year",
    "Published",
]
GENRE_LABELS = ["Жанр", "Категорія", "Розділ", "Genre", "Category"]
DESCRIPTION_LABELS = ["Опис", "Анотація", "Про книгу", "Description", "Annotation"]


def enrich_metadata_from_html(metadata, html):
    metadata = dict(metadata)
    metadata["author"] = clean_labeled_value(metadata.get("author", ""))
    metadata["publisher"] = clean_labeled_value(metadata.get("publisher", ""))
    metadata["genre"] = clean_labeled_value(metadata.get("genre", ""))
    metadata["author"] = metadata.get("author") or extract_labeled_value(html, AUTHOR_LABELS)
    metadata["publisher"] = metadata.get("publisher") or extract_labeled_value(html, PUBLISHER_LABELS)
    metadata["publisher"] = metadata.get("publisher") or extract_jsonish_value(
        html,
        (
            "publisher",
            "publisherName",
            "publisher_name",
            "publishingHouse",
            "publishing_house",
            "manufacturer",
        ),
        PUBLISHER_LABELS,
    )
    metadata["published_year"] = metadata.get("published_year") or parse_published_year(
        extract_labeled_value(html, PUBLISHED_YEAR_LABELS)
        or extract_jsonish_value(
            html,
            (
                "publishedYear",
                "publicationYear",
                "publication_year",
                "publishYear",
                "yearPublished",
                "year",
                "datePublished",
                "published_at",
            ),
            PUBLISHED_YEAR_LABELS,
        )
    )
    metadata["genre"] = metadata.get("genre") or extract_labeled_value(html, GENRE_LABELS)
    metadata["description"] = metadata.get("description") or extract_labeled_value(html, DESCRIPTION_LABELS)
    return metadata


def extract_labeled_value(html, labels):
    import re

    visible_html = remove_non_content_tags(html)
    for label in labels:
        structured_patterns = (
            rf"<(?:dt|th)[^>]*>\s*{re.escape(label)}\s*:?[\s\u00a0]*</(?:dt|th)>\s*<(?:dd|td)[^>]*>(.*?)</(?:dd|td)>",
            rf"<(?:span|div|p|li)[^>]*>\s*{re.escape(label)}\s*:?[\s\u00a0]*</(?:span|div|p|li)>\s*<(?:span|div|p|a)[^>]*>(.*?)</(?:span|div|p|a)>",
        )
        for pattern in structured_patterns:
            match = re.search(pattern, visible_html, re.IGNORECASE | re.DOTALL)
            if match:
                value = clean_labeled_value(match.group(1))
                if value:
                    return value

        container_patterns = (
            rf"<(?:li|div|p|tr)[^>]*>[^<]*(?:<[^>]+>[^<]*)*{re.escape(label)}\s*:?(.*?)</(?:li|div|p|tr)>",
        )
        for pattern in container_patterns:
            for match in re.finditer(pattern, visible_html, re.IGNORECASE | re.DOTALL):
                value_html = re.sub(rf"^.*?{re.escape(label)}\s*:?[\s\u00a0]*", "", match.group(1),
                                    flags=re.IGNORECASE | re.DOTALL)
                value = clean_labeled_value(value_html)
                if value:
                    return value

    text = strip_tags(visible_html)
    stop_labels = tuple(
        dict.fromkeys(AUTHOR_LABELS + PUBLISHER_LABELS + PUBLISHED_YEAR_LABELS + GENRE_LABELS + DESCRIPTION_LABELS + [
            "ISBN", "Кількість сторінок", "Палітурка", "Мова", "Формат", "Language", "Pages",
        ]))
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


def extract_jsonish_value(html, keys, labels=()):
    import re

    searchable = unescape_html(html)
    quoted_string = r'["\']([^"\']{2,180})["\']'

    for key in keys:
        key_pattern = re.escape(key)
        match = re.search(rf'["\']{key_pattern}["\']\s*:\s*{quoted_string}', searchable, re.IGNORECASE)
        if match:
            value = clean_labeled_value(match.group(1))
            if value:
                return value

    for label in labels:
        label_pattern = re.escape(label)
        patterns = (
            rf'["\'](?:name|label|title|frontend_label|attribute_label)["\']\s*:\s*["\']{label_pattern}["\'][^{{}}]{{0,320}}?["\'](?:value|values|text|option|display_value)["\']\s*:\s*{quoted_string}',
            rf'["\'](?:value|values|text|option|display_value)["\']\s*:\s*{quoted_string}[^{{}}]{{0,320}}?["\'](?:name|label|title|frontend_label|attribute_label)["\']\s*:\s*["\']{label_pattern}["\']',
        )
        for pattern in patterns:
            match = re.search(pattern, searchable, re.IGNORECASE | re.DOTALL)
            if match:
                value = clean_labeled_value(match.group(1))
                if value and value.casefold() != label.casefold():
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
        "наявності", "товар", "характеристики", "відгук", "додати", "обране",
        "booknest", "yakaboo", "readeat", "google", "open library",
    )
    if any(fragment in lowered for fragment in rejected_fragments):
        return ""

    service_value_patterns = ("_label", "book_", "attribute_", "::", "{{", "}}")
    if any(pattern in lowered for pattern in service_value_patterns):
        return ""

    return value


def finalize_metadata(metadata, base_url=""):
    metadata = dict(metadata)
    for field in ("author", "publisher", "genre"):
        metadata[field] = clean_labeled_value(metadata.get(field, ""))
    metadata["title"] = strip_title_suffix(strip_tags(metadata.get("title", "")))
    metadata["description"] = strip_tags(metadata.get("description", ""))
    metadata["cover_url"] = normalize_absolute_url(metadata.get("cover_url", ""), base_url)
    metadata["external_url"] = normalize_absolute_url(metadata.get("external_url", ""), base_url)
    return metadata


def normalize_absolute_url(url, base_url=""):
    url = str(url or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if base_url:
        return urljoin(base_url, url)
    return url


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