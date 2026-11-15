"""Bounded public HTTP requests using validated, pinned destination addresses."""
import http.client
import ipaddress
import socket
import ssl

import certifi
from urllib.parse import urlsplit, urljoin, urlunsplit


def destination(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ("https","http") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use a public HTTP or HTTPS URL without credentials.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("This URL resolves to a private or restricted address.")
    return parsed, port, addresses[0][4][0]


def fetch(url):
    for _ in range(5):
        parsed, port, address = destination(url)
        connection = http.client.HTTPConnection(parsed.hostname,port,timeout=10)
        try:
            sock = socket.create_connection((address,port),timeout=10)
            if parsed.scheme == "https":
                sock = ssl.create_default_context(cafile=certifi.where()).wrap_socket(sock,server_hostname=parsed.hostname)
            connection.sock = sock
            path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
            connection.request("GET",path,headers={"User-Agent":"CrackMate/2.0 (selected-source import)","Accept-Encoding":"identity"})
            response = connection.getresponse()
            if response.status in (301,302,303,307,308):
                url = urljoin(url,response.getheader("Location",""))
                continue
            if response.status != 200:
                raise ValueError(f"Source returned HTTP {response.status}. Paste text or upload a permitted copy.")
            if response.getheader("Content-Encoding","identity") != "identity":
                raise ValueError("Compressed responses are unsupported. Upload or paste the source.")
            mime = response.getheader("Content-Type","").split(";")[0]
            if mime not in ("text/html","text/plain","text/markdown","application/pdf","application/json"):
                raise ValueError("Unsupported source type.")
            data = response.read(2_000_001)
            if len(data)>2_000_000:
                raise ValueError("Source exceeds the 2 MB download limit.")
            return url,mime,data
        except (OSError,http.client.HTTPException):
            raise ValueError("Source could not be reached safely. Paste text or upload a file.") from None
        finally:
            connection.close()
    raise ValueError("Too many redirects.")


def extract(name,data,mime=""):
    if len(data)>2_000_000:
        raise ValueError("File exceeds 2 MB.")
    if name.lower().endswith(".pdf") or mime=="application/pdf":
        from core.resume import read_upload, Limits
        return read_upload("source.pdf",data,Limits(file_bytes=2_000_000,pages=30,text_chars=100000))
    text=data.decode("utf-8-sig",errors="strict")
    if mime=="text/html":
        import trafilatura
        text=trafilatura.extract(text,include_tables=True,output_format="txt") or ""
    if not text.strip() or len(text)>100000:
        raise ValueError("Extraction was empty or exceeded 100,000 characters.")
    return text
