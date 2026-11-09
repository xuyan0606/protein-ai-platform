from app.services.task_execution_contract import build_task_execution_quote, validate_task_execution_quote


def test_long_task_quote_requires_confirmation_and_is_not_billing_authorization():
    quote = build_task_execution_quote(
        tool_name="gromacs_md",
        params={"replicates": 3, "pdb_object": "sample.pdb"},
        queue="md_cpu",
        soft_time_limit=3600,
        time_limit=7200,
    )

    assert quote["long_task"] is True
    assert quote["requires_user_confirmation"] is True
    assert quote["execution_allowed"] is False
    assert quote["billing_adapter_connected"] is False
    assert quote["final_cost"] is None
    assert quote["input_sha256"]
    assert validate_task_execution_quote(quote) == []


def test_short_task_quote_is_still_auditable_without_blocking_execution():
    quote = build_task_execution_quote(
        tool_name="esmfold_folding",
        params={"sequence": "ACDE"},
        queue="default",
        soft_time_limit=60,
        time_limit=120,
    )

    assert quote["long_task"] is False
    assert quote["requires_user_confirmation"] is False
    assert quote["execution_allowed"] is True
    assert validate_task_execution_quote(quote) == []
