from scripts.check_app import main


def test_offline_check_reports_ready(capsys):
    main()
    output = capsys.readouterr().out
    assert "offline_checks_ok=True" in output