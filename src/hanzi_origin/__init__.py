__version__ = None

from pathlib import Path

def get_version():
    global __version__
    if __version__ is None:
        version_file = Path(__file__).parent.parent.parent / "version.txt"
        __version__ = version_file.read_text().strip()
    return __version__
