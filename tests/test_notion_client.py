from drone_billing.notion_client import NotionClient, parse_notion_page


def test_parse_notion_page_rollup_acres():
    page = {
        "id": "3e9284de-cb43-80a7-a259-e2e18203b8c5",
        "properties": {
            "Project Number": {
                "title": [{"plain_text": "1575-Mid Valley Unit4_PH2"}],
            },
            "Project": {"relation": [{"id": "proj-abc"}]},
            "Flight Date": {"date": {"start": "2026-09-28"}},
            "Flight Type": {"select": {"name": "Progress"}},
            "Drone Equipment": {"select": {"name": "Wingtra Ray"}},
            "Acres": {"rollup": {"type": "number", "number": 200}},
            "Status": {"select": {"name": "Completed"}},
        },
    }
    flight = parse_notion_page(page, {"proj-abc": "1575 Mid Valley"})
    assert flight.acres == 200
    assert flight.project_number == "1575"
    assert flight.status == "Completed"


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"results": [], "has_more": False}


class _FakeHttp:
    def __init__(self) -> None:
        self.payload = None

    def post(self, url, json=None):
        self.payload = json
        return _FakeResponse()


def test_query_filter_includes_in_process_and_completed():
    http = _FakeHttp()
    client = NotionClient(token="test", http_client=http)
    pages = client.query_database_pages()
    assert pages == []
    statuses = {item["select"]["equals"] for item in http.payload["filter"]["or"]}
    assert statuses == {"Completed", "In Process"}
