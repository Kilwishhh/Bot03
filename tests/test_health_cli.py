from app.main import main


def test_paper_health_checks_adapter(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["crypto-bot", "health"])
    main()
    assert "exchange_reachable=True" in capsys.readouterr().out
