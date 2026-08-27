from scripts.run_backtest import main


def test_backtest_script_reports_unvalidated_performance(capsys):
    main()
    assert "Performance not yet validated." in capsys.readouterr().out
