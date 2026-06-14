"""
Local override for Arcade's PyInstaller hook.

Arcade 3.3.3's bundled hook places VERSION at arcade/VERSION/VERSION,
which makes arcade.version try to read a directory at runtime.
"""

from importlib.util import find_spec
from pathlib import Path

from PyInstaller.compat import is_darwin, is_unix, is_win

if not is_win and not is_darwin and not is_unix:
    raise NotImplementedError(
        "You are running on an unsupported operating system. "
        "Only Linux, Mac, and Windows are supported."
    )

hiddenimports = ["arcade.gl.backends.opengl.provider", "arcade.gl.backends.opengl"]

datas = []
binaries = []

arcade_spec = find_spec("arcade")
if arcade_spec is None or arcade_spec.origin is None:
    raise ImportError("Arcade is not installed. Cannot continue.")

arcade_path = Path(arcade_spec.origin).parent
datas.extend(
    [
        (
            arcade_path / "resources" / "system",
            "arcade/resources/system",
        ),
        (
            arcade_path / "VERSION",
            "arcade",
        ),
    ]
)

if is_darwin:
    binaries.append((arcade_path / "lib", "arcade/lib"))

pymunk_spec = find_spec("pymunk")
if pymunk_spec is not None and pymunk_spec.origin is not None:
    pymunk_path = Path(pymunk_spec.origin).parent

    if is_win:
        binaries.append((pymunk_path / "_chipmunk.pyd", "."))
    elif is_darwin:
        binaries.append((pymunk_path / "_chipmunk.abi3.so", "."))
    elif is_unix:
        binaries.append((pymunk_path / "_chipmunk.abi3.so", "."))
else:
    print("Pymunk is not available. Skipping Pymunk resources.")
