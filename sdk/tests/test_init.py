from autopulse import autopulse, monitor


def test_monitor_accepts_app() -> None:
    monitor(object())


def test_autopulse_accepts_app() -> None:
    autopulse(object())
