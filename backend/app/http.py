from urllib.parse import quote


def attachment(filename: str) -> str:
    return f"attachment; filename*=UTF-8''{quote(filename)}"
