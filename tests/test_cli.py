import pytest
from typer.testing import CliRunner

from likeforlike.cli import app

runner = CliRunner()


@pytest.fixture(scope="module")
def workspace(tmp_path_factory):
    root = tmp_path_factory.mktemp("ws")
    result = runner.invoke(app, ["generate", "--seed", "7", "--out", str(root / "raw")])
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        app,
        [
            "build",
            "--raw",
            str(root / "raw"),
            "--out",
            str(root / "mart"),
            "--pbip",
            str(root / "pbi"),
        ],
    )
    assert result.exit_code == 0, result.output
    return root


def test_generate_reports_counts(workspace):
    assert (workspace / "raw" / "weekly_sales.csv").exists()
    assert (workspace / "raw" / "truth.json").exists()


def test_build_writes_mart_and_pbip_and_reports_zero_residual(workspace):
    assert len(list((workspace / "mart").glob("*.csv"))) == 4
    assert (workspace / "pbi" / "LikeForLike.pbip").exists()


def test_lfl_by_month_prints_twelve_months(workspace):
    result = runner.invoke(
        app, ["lfl", "--year", "2024", "--by", "month", "--raw", str(workspace / "raw")]
    )
    assert result.exit_code == 0, result.output
    assert "FY2024 like-for-like by fiscal month" in result.output
    for month in ("Feb", "Nov", "Dec", "Jan"):
        assert month in result.output


def test_bridge_prints_all_buckets_and_zero_residual(workspace):
    result = runner.invoke(app, ["bridge", "--year", "2024", "--raw", str(workspace / "raw")])
    assert result.exit_code == 0, result.output
    for bucket in ("comp", "new_store", "closed_store", "refurbishment", "extra_week"):
        assert bucket in result.output
    assert "< 1e-9" in result.output


def test_policy_diff_flags_select_variants(workspace):
    raw = str(workspace / "raw")
    only_ramp = runner.invoke(app, ["policy-diff", "--no-ramp", "--raw", raw])
    assert "no ramp exclusion" in only_ramp.output and "no restatement" not in only_ramp.output
    only_restate = runner.invoke(app, ["policy-diff", "--no-restate", "--raw", raw])
    assert (
        "no restatement" in only_restate.output and "no ramp exclusion" not in only_restate.output
    )
    both = runner.invoke(app, ["policy-diff", "--raw", raw])
    assert "no ramp exclusion" in both.output and "no restatement" in both.output


def test_validate_pbip_passes_then_fails_after_a_column_rename(workspace):
    args = ["validate-pbip", "--pbip", str(workspace / "pbi"), "--data", str(workspace / "mart")]
    assert runner.invoke(app, args).exit_code == 0
    path = workspace / "mart" / "GrowthBridge.csv"
    original = path.read_text()
    path.write_text(original.replace("sales_ly", "sales_prior", 1))
    try:
        result = runner.invoke(app, args)
        assert result.exit_code == 1
        assert "sales_ly" in result.output
    finally:
        path.write_text(original)


def test_missing_raw_data_is_a_clear_error(tmp_path):
    result = runner.invoke(app, ["lfl", "--raw", str(tmp_path / "nope")])
    assert result.exit_code == 2 and "likeforlike generate" in result.output


def test_unknown_period_exits_with_an_error(workspace):
    result = runner.invoke(app, ["lfl", "--by", "decade", "--raw", str(workspace / "raw")])
    assert result.exit_code == 2
