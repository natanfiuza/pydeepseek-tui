import os


def is_path_allowed(file_path: str, allowed_dirs: list[str] | None = None) -> bool:
    """Verifica se o caminho resolvido esta dentro dos diretorios permitidos."""
    if allowed_dirs is None:
        allowed_dirs = [os.getcwd()]

    try:
        real_path = os.path.realpath(file_path)
    except (ValueError, OSError):
        return False

    for allowed_dir in allowed_dirs:
        real_allowed = os.path.realpath(allowed_dir)
        if os.path.commonpath([real_path, real_allowed]) == real_allowed:
            return True

    return False
