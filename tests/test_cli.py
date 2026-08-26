from app.main import main


def test_cli_parser_accepts_paper_demo(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["crypto-bot", "paper-demo"])
    main()
    assert "order_status=FILLED" in capsys.readouterr().out


def test_status_reports_provider(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["crypto-bot", "status"])
    main()
    assert "provider=binance" in capsys.readouterr().out


def test_start_runs_one_safe_paper_cycle(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("sys.argv", ["crypto-bot", "start", "--mode", "paper"])
    monkeypatch.chdir(tmp_path)
    main()
    assert "bot completed cycles=1" in capsys.readouterr().out