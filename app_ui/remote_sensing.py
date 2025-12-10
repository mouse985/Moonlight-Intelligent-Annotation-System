_remote_sensing_enabled: bool = False

def is_remote_sensing_enabled() -> bool:
    return bool(_remote_sensing_enabled)

def set_remote_sensing_enabled(enabled: bool) -> None:
    global _remote_sensing_enabled
    _remote_sensing_enabled = bool(enabled)
