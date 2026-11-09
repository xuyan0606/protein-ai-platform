from app.services.tool_baseline_manifest import reconcile_tool_baseline


def test_load_catalog_tool_names_extracts_markdown_registry(tmp_path):
    from app.services.tool_baseline_manifest import load_catalog_tool_names

    catalog = tmp_path / "catalog.md"
    catalog.write_text("| `alpha_tool` | false |\n| `beta_tool` | true |\n", encoding="utf-8")
    assert load_catalog_tool_names(catalog) == ["alpha_tool", "beta_tool"]


def test_reconcile_tool_baseline_marks_runtime_gaps_without_rewriting_catalog():
    result = reconcile_tool_baseline(
        desired_tools=["enzyme_identity_profile", "scientific_claim_gate", "missing_tool"],
        runtime_tools=["enzyme_identity_profile", "scientific_claim_gate"],
    )

    rows = {row["tool_id"]: row for row in result["entries"]}
    assert result["catalog_tool_count"] == 3
    assert result["runtime_tool_count"] == 2
    assert rows["enzyme_identity_profile"]["runtime_state"] == "available"
    assert rows["missing_tool"]["runtime_state"] == "pending_reconnect"
    assert rows["missing_tool"]["fallback_tool"] is None
    assert rows["missing_tool"]["fallback_level"] is None
    assert result["summary"]["pending_reconnect"] == 1


def test_reconcile_tool_baseline_marks_declared_runtime_fallback_as_degraded():
    result = reconcile_tool_baseline(
        desired_tools=["catalytic_site_lookup"],
        runtime_tools=["enzyme_identity_profile"],
        fallback_map={"catalytic_site_lookup": "enzyme_identity_profile"},
    )

    assert result["entries"][0]["runtime_state"] == "degraded"
    assert result["entries"][0]["fallback_tool"] == "enzyme_identity_profile"
    assert result["entries"][0]["configured_fallback_tool"] == "enzyme_identity_profile"
    assert result["entries"][0]["fallback_level"] == "DEGRADED"


def test_reconcile_tool_baseline_does_not_select_an_unavailable_configured_fallback():
    result = reconcile_tool_baseline(
        desired_tools=["catalytic_site_lookup"],
        runtime_tools=[],
        fallback_map={"catalytic_site_lookup": "enzyme_identity_profile"},
    )

    row = result["entries"][0]
    assert row["runtime_state"] == "pending_reconnect"
    assert row["configured_fallback_tool"] == "enzyme_identity_profile"
    assert row["fallback_tool"] is None
    assert row["fallback_level"] is None
