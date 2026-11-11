"""Prepare an isolated desktop installation and launch it (Python 3.10–3.14)."""
from pathlib import Path
import subprocess
import sys
import venv


def main():
    if not (3, 10) <= sys.version_info[:2] < (3, 15):
        print('PetaRelasi Studio memerlukan Python 3.10 sampai 3.14, sesuai versi Qt yang digunakan.')
        return 2
    root = Path(__file__).resolve().parent
    environment = root / '.venv'
    interpreter = environment / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    try:
        if not interpreter.is_file():
            print('Menyiapkan lingkungan PetaRelasi Studio…', flush=True)
            venv.EnvBuilder(with_pip=True).create(environment)
        check = subprocess.run(
            [str(interpreter), '-c', 'from importlib.metadata import version; '
             'from petarelasi import __version__; from PySide6 import QtWidgets; import sqlglot; '
             'assert version("petarelasi") == __version__'],
            cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if check.returncode:
            print('Memasang aplikasi dan dependensi. Proses pertama memerlukan internet…', flush=True)
            result = subprocess.run([str(interpreter), '-m', 'pip', 'install', str(root) + '[app]'], cwd=root)
            if result.returncode:
                print('Instalasi belum berhasil. Periksa koneksi dan pesan di atas, lalu jalankan kembali.')
                return result.returncode
        return subprocess.run([str(interpreter), '-m', 'petarelasi', 'app'], cwd=root).returncode
    except (OSError, subprocess.SubprocessError) as exc:
        print('Studio tidak dapat dijalankan. ' + str(exc))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
