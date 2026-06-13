import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
OPEN_LIBRARY_COVER_URL = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
OPEN_LIBRARY_WORK_URL = "https://openlibrary.org{key}"
USER_AGENT = "BookNest demo app (Open Library search; contact: demo@booknest.local)"


class BookLookupError(Exception):
    pass


def search_open_library_books(query, limit=8):
    query = query.strip()
    if not query:
        return []

    params = urlencode(
        {
            "title": query,
            "limit": limit,
            "fields": "key,title,author_name,first_publish_year,publisher,subject,cover_i",
        }
    )
    request = Request(
        f"{OPEN_LIBRARY_SEARCH_URL}?{params}",
        headers={"User-Agent": USER_AGENT},
    )

    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise BookLookupError("Не вдалося отримати дані з Open Library. Спробуйте ще раз пізніше.") from exc

    return [normalize_open_library_doc(doc) for doc in payload.get("docs", [])]


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
    }