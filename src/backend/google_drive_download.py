"""Public Google Drive file downloads, including the large-file confirmation."""
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urlsplit
import re

from services.i18n_message import message


def file_id(url: str) -> str:
    try:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or parts.hostname not in {
                "drive.google.com", "drive.usercontent.google.com"}:
            return ""
        match = re.fullmatch(r"/file/d/([\w-]+)(?:/.*)?", parts.path)
        value = match[1] if match else parse_qs(parts.query).get("id", [""])[0]
        return value if re.fullmatch(r"[\w-]+", value) else ""
    except ValueError:
        return ""


def download_url(url: str) -> str:
    params = {"id": file_id(url), "export": "download"}
    key = parse_qs(urlsplit(url).query).get("resourcekey", [""])[0]
    if key:
        params["resourcekey"] = key
    return "https://drive.usercontent.google.com/download?" + urlencode(params)


class ConfirmationForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = ""
        self.fields = {}
        self.inside = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("id") == "download-form":
            self.inside = True
            self.action = attrs.get("action", "")
        if self.inside and tag == "input" and attrs.get("name"):
            self.fields[attrs["name"]] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.inside = False


def open_download(session, url, *, headers, timeout):
    """Return a streaming response; never save an error/login HTML as an archive."""
    current = download_url(url)
    for _ in range(3):
        resp = session.get(current, stream=True, timeout=timeout, headers=headers)
        if resp.status_code == 416:
            return resp
        resp.raise_for_status()
        if "text/html" not in resp.headers.get("Content-Type", "").lower():
            return resp
        try:
            # Bound the response: a login/quota page is not an archive.
            body = bytearray()
            for chunk in resp.iter_content(chunk_size=16384):
                body.extend(chunk)
                if len(body) > 1024 * 1024:
                    raise ValueError(message("download.drive.unavailable"))
            form = ConfirmationForm()
            form.feed(body.decode("utf-8", errors="replace"))
        finally:
            resp.close()
        parts = urlsplit(form.action)
        if (parts.scheme != "https" or parts.hostname != "drive.usercontent.google.com"
                or parts.path != "/download" or form.fields.get("id") != file_id(url)
                or not form.fields.get("confirm")):
            raise ValueError(message("download.drive.unavailable"))
        current = form.action + "?" + urlencode(form.fields)
    raise ValueError(message("download.drive.unavailable"))
