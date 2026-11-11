"""Optional PetaRelasi Studio desktop interface."""
import sys


def run():
    try:
        from .window import launch
    except ImportError as exc:
        if exc.name and exc.name.startswith(('PySide6', 'shiboken6')):
            print('Antarmuka belum dipasang. Jalankan python -m pip install ".[app]".', file=sys.stderr)
            return 2
        raise
    return launch()
