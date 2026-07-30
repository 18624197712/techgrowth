import re
from urllib.parse import urlparse


def canonical_remote_url(remote: str) -> str:
    value = remote.strip()
    if not value:
        return ""
    scp_match = re.fullmatch(r"(?:[^@/]+@)?([^:/]+):(.+)", value)
    if scp_match and "://" not in value:
        host, path = scp_match.groups()
    else:
        parsed = urlparse(value if "://" in value else f"https://{value}")
        host, path = parsed.hostname or "", parsed.path
    normalized_path = path.strip("/")
    if normalized_path.casefold().endswith(".git"):
        normalized_path = normalized_path[:-4]
    if not host or not normalized_path:
        return ""
    return f"{host.casefold()}/{normalized_path.casefold()}"
