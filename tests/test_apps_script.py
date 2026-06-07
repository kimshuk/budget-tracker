from pathlib import Path


CODE = Path("apps_script/Code.gs").read_text(encoding="utf-8")


def test_apps_script_installs_budget_tracker_edit_trigger():
    assert 'getHandlerFunction() === "handleBudgetTrackerEdit"' in CODE
    assert 'newTrigger("handleBudgetTrackerEdit")' in CODE


def test_apps_script_handles_category_list_edits():
    assert "function isCategoryListEdit_" in CODE
    assert "refreshMerchantCategoryValidation_" in CODE
    assert "isCategoryListEdit_(e.range)" in CODE


def test_apps_script_keeps_legacy_merchant_category_handler():
    assert "function handleMerchantCategoryEdit(e)" in CODE
    assert "handleBudgetTrackerEdit(e);" in CODE
