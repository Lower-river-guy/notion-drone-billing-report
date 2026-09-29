from drone_billing.notion_client import parse_notion_page


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
