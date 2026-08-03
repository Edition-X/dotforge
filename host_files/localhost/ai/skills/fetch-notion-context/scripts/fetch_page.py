#!/usr/bin/env python3
"""Fetch a Notion page's block tree as markdown-ish text."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"


def page_id_from(value: str) -> str:
    value = value.strip()
    match = re.search(r"([0-9a-fA-F]{32})(?:[?#/]|$)", value.replace("-", ""))
    if match:
        raw = match.group(1)
    else:
        raw = re.sub(r"[^0-9a-fA-F]", "", value)
    if len(raw) != 32:
        raise SystemExit("Could not parse a 32-character Notion page ID from input")
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"


def request(path: str) -> dict:
    token = os.environ.get("NOTION_API_KEY")
    if not token:
        raise SystemExit("NOTION_API_KEY is not set")
    req = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise SystemExit(f"Notion API error {exc.code}: {body}") from exc


def rich_text(items: list[dict]) -> str:
    return "".join(item.get("plain_text", "") for item in items or [])


def title_from_page(page: dict) -> str:
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            return rich_text(prop.get("title", [])) or "Untitled"
    return "Untitled"


def block_text(block: dict) -> str:
    typ = block.get("type")
    data = block.get(typ, {}) if typ else {}
    text = rich_text(data.get("rich_text", []))
    if typ and typ.startswith("heading_"):
        level = typ.rsplit("_", 1)[1]
        return f"{'#' * int(level)} {text}"
    if typ == "bulleted_list_item":
        return f"- {text}"
    if typ == "numbered_list_item":
        return f"1. {text}"
    if typ == "to_do":
        return f"[{'x' if data.get('checked') else ' '}] {text}"
    if typ == "quote":
        return f"> {text}"
    if typ == "callout":
        return f"Callout: {text}"
    if typ == "code":
        lang = data.get("language", "")
        return f"```{lang}\n{text}\n```"
    if typ == "paragraph":
        return text
    if typ == "child_page":
        return f"Child page: {data.get('title', '')}"
    return text or f"[{typ}]"


def fetch_blocks(block_id: str, indent: int = 0) -> list[str]:
    lines: list[str] = []
    cursor = None
    while True:
        query = f"?start_cursor={urllib.parse.quote(cursor)}" if cursor else ""
        data = request(f"/blocks/{block_id}/children?page_size=100{query}")
        for block in data.get("results", []):
            line = block_text(block)
            if line.strip():
                lines.append(f"{'  ' * indent}{line}")
            if block.get("has_children"):
                lines.extend(fetch_blocks(block["id"], indent + 1))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return lines


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: fetch_page.py <notion-url-or-page-id>", file=sys.stderr)
        return 2
    page_id = page_id_from(sys.argv[1])
    page = request(f"/pages/{page_id}")
    print(f"# {title_from_page(page)}")
    print(f"Page ID: {page_id}")
    print()
    print("\n".join(fetch_blocks(page_id)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
