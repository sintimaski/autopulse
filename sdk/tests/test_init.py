from autopulse import monitor


def test_monitor_accepts_app() -> None:
    monitor(object())
