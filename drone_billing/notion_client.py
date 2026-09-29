"""Notion REST API client for Drone Flight Schedule."""

from __future__ import annotations

import os
from datetime import date
from typing import Any, Protocol

import httpx

from drone_billing.billing import (
    REQUIRED_NOTION_PROPERTIES,
    FlightRecord,
    parse_project_number_and_name,
)

DEFAULT_DATABASE_ID = "16f9d45a816849cf9436ed2a566312b3"
NOTION_API_BASE = "https://api.notion.com/v1"
DEFAULT_NOTION_VERSION = "2022-06-28"


class NotionClientProtocol(Protocol):
    def validate_schema(self) -> None: ...
    def query_flights(self) -> list[FlightRecord]: ...


def _page_url(page_id: str) -> str:
    clean = page_id.replace("-", "")
    return f"https://app.notion.com/{clean}"


def _extract_title(prop: dict[str, Any]) -> str:
    title_list = prop.get("title") or []
    return "".join(part.get("plain_text", "") for part in title_list)


def _extract_select(prop: dict[str, Any]) -> str | None:
    sel = prop.get("select")
    if sel is None:
        return None
    return sel.get("name")


def _extract_date(prop: dict[str, Any]) -> date | None:
    d = prop.get("date")
    if not d or not d.get("start"):
        return None
    start = d["start"][:10]
    return date.fromisoformat(start)


def _extract_relation_ids(prop: dict[str, Any]) -> list[str]:
    return [r["id"] for r in prop.get("relation") or []]


def _extract_rollup_number(prop: dict[str, Any]) -> int | None:
    rollup = prop.get("rollup") or {}
    rollup_type = rollup.get("type")
    if rollup_type == "number":
        val = rollup.get("number")
        if val is None:
            return None
        return int(round(val))
    if rollup_type == "array":
        arr = rollup.get("array") or []
        total = 0.0
        found = False
        for item in arr:
            if item.get("type") == "number" and item.get("number") is not None:
                total += float(item["number"])
                found = True
        if not found:
            return None
        return int(round(total))
    return None


def parse_notion_page(page: dict[str, Any], project_titles: dict[str, str]) -> FlightRecord:
    props = page.get("properties") or {}
    page_id = page["id"]
    title = _extract_title(props.get("Project Number") or {})
    relation_ids = _extract_relation_ids(props.get("Project") or {})
    related_title = None
    if len(relation_ids) == 1:
        related_title = project_titles.get(relation_ids[0])
    project_number, project_name = parse_project_number_and_name(title, related_title)

    return FlightRecord(
        page_id=page_id,
        page_url=_page_url(page_id),
        title=title,
        project_number=project_number,
        project_name=project_name,
        flight_date=_extract_date(props.get("Flight Date") or {}),
        flight_type=_extract_select(props.get("Flight Type") or {}),
        drone_equipment=_extract_select(props.get("Drone Equipment") or {}),
        acres=_extract_rollup_number(props.get("Acres") or {}),
        status=_extract_select(props.get("Status") or {}),
        project_relation_ids=relation_ids,
    )


class NotionClient:
    def __init__(
        self,
        token: str,
        database_id: str | None = None,
        notion_version: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.database_id = (database_id or os.environ.get("NOTION_DATABASE_ID") or DEFAULT_DATABASE_ID).replace(
            "-", ""
        )
        self.notion_version = notion_version or os.environ.get("NOTION_VERSION", DEFAULT_NOTION_VERSION)
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": self.notion_version,
            "Content-Type": "application/json",
        }
        self._client = http_client or httpx.Client(base_url=NOTION_API_BASE, headers=headers, timeout=60.0)
        self._owns_client = http_client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def retrieve_database(self) -> dict[str, Any]:
        r = self._client.get(f"/databases/{self.database_id}")
        r.raise_for_status()
        return r.json()

    def validate_schema(self) -> None:
        db = self.retrieve_database()
        props = db.get("properties") or {}
        names = set(props.keys())
        missing = REQUIRED_NOTION_PROPERTIES - names
        if missing:
            raise RuntimeError(
                f"Notion database missing required properties: {sorted(missing)}. "
                f"Found: {sorted(names)}"
            )

    def query_database_pages(self) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        payload: dict[str, Any] = {"page_size": 100}
        while True:
            r = self._client.post(f"/databases/{self.database_id}/query", json=payload)
            r.raise_for_status()
            data = r.json()
            pages.extend(data.get("results") or [])
            if not data.get("has_more"):
                break
            payload["start_cursor"] = data["next_cursor"]
        return pages

    def retrieve_page(self, page_id: str) -> dict[str, Any]:
        r = self._client.get(f"/pages/{page_id}")
        r.raise_for_status()
        return r.json()

    def _fetch_project_titles(self, relation_ids: set[str]) -> dict[str, str]:
        titles: dict[str, str] = {}
        for pid in relation_ids:
            try:
                page = self.retrieve_page(pid)
                props = page.get("properties") or {}
                for _name, prop in props.items():
                    if prop.get("type") == "title":
                        titles[pid] = _extract_title(prop)
                        break
            except httpx.HTTPError:
                titles[pid] = ""
        return titles

    def query_flights(self) -> list[FlightRecord]:
        pages = self.query_database_pages()
        relation_ids: set[str] = set()
        for page in pages:
            props = page.get("properties") or {}
            for rid in _extract_relation_ids(props.get("Project") or {}):
                relation_ids.add(rid)
        project_titles = self._fetch_project_titles(relation_ids)
        return [parse_notion_page(p, project_titles) for p in pages]
