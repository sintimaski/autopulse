from lumonox import lumonox, monitor


def test_monitor_accepts_app() -> None:
    monitor(object())


def test_lumonox_accepts_app() -> None:
    lumonox(object())
