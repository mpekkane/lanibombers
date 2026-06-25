import shutil
import sys
from typing import Union, TypeVar, Callable, List, Any
import yaml
from pathlib import Path


T = TypeVar("T")

# Configs the user is expected to edit outside the packaged exe. These are kept
# next to the executable (rather than inside the read-only PyInstaller bundle)
# and seeded from the bundled defaults on first run. Matched by file name, so
# every ConfigReader call referencing them is routed externally automatically.
USER_EDITABLE_CONFIGS = {"client_config.yaml", "player.yaml"}


def _base_dir() -> Path:
    """
    Returns the base directory where bundled resources live.
    - Dev: project root (parent of 'common/')
    - PyInstaller: sys._MEIPASS (onefile temp dir / onedir bundle dir)
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)

    # dev mode: common/ is a package folder, so go one up to project root
    return Path(__file__).resolve().parent.parent


def _external_dir() -> Path:
    """
    Returns the directory for user-editable files that must persist outside the
    bundle.
    - Dev: project root (parent of 'common/')
    - PyInstaller: the folder containing the executable
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


def resource_path(relative: str | Path) -> Path:
    return _base_dir() / Path(relative)


def user_config_path(relative: str | Path) -> Path:
    """
    Resolve a user-editable config path next to the executable.

    On first run the file won't exist there yet, so it is seeded from the
    bundled default (if present) so the user has something to edit. In dev mode
    the external and bundled locations are the same, so this is a no-op.
    """
    relative = Path(relative)
    external = _external_dir() / relative
    if not external.exists():
        bundled = resource_path(relative)
        if bundled.exists() and bundled.resolve() != external.resolve():
            external.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundled, external)
    return external


class ConfigReader:
    """YAML Config reader class"""

    def __init__(self, config_file: str):
        if Path(config_file).name in USER_EDITABLE_CONFIGS:
            cfg_path = user_config_path(config_file)
        else:
            cfg_path = resource_path(config_file)
        if Path(cfg_path).exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {}

    def get_config(self, field: str, t: Callable[[str], T] = str) -> Union[T, None]:
        """Get config value

        Args:
            field (str): config key
            t (Callable[[str], T]): type to which the value is casted. Defaults to str.

        Returns:
            Union[T, None, str]: Value, or if not found, None
        """

        if field in self.config:
            if (
                isinstance(self.config[field], str)
                and self.config[field].lower() == "none"
            ):
                return None
            if isinstance(t, str):
                return self.config[field]
            else:
                return t(self.config[field])
        else:
            return None

    def get_config_mandatory(self, field: str, t: Callable[[str], T] = str) -> T:
        """Get config value

        Args:
            field (str): config key
            t (Callable[[str], T]): type to which the value is casted. Defaults to str.

        Returns:
            Union[T, None, str]: Value, or if not found, None
        """

        if field in self.config:
            if (
                isinstance(self.config[field], str)
                and self.config[field].lower() == "none"
            ):
                raise ValueError("Field value is None")
            if isinstance(t, str):
                return self.config[field]
            else:
                return t(self.config[field])
        else:
            raise ValueError("Field value not in configuration file")

    def get_config_def(
        self,
        field: str,
        t: Union[Union[str, Callable], List[Union[str, Callable]]],
        default: T,
    ) -> T:
        """Get config value

        Args:
            field (str): config key
            t (Union[str, Callable]): type to which the value is casted.
               Defaults to str.

        Returns:
            Union[T, None, str]: Value, or if not found, None
        """
        if self is None or self.config is None or not self.config:
            return default

        if field in self.config:
            if isinstance(t, list):
                success = False
                val = None
                for typ in t:
                    try:
                        val = self.get_config_def(field, typ, default)
                        success = True
                        break
                    except Exception:
                        pass
                if success and val is not None:
                    return val
                else:
                    return default
            else:
                val = self.config[field]
                if isinstance(val, str) and val.lower() == "none":
                    return default
                return t(val)  # type: ignore
        else:
            return default

    def get_config_untyped(self, field: str) -> Union[Any, None]:
        """Get config value

        Args:
            field (str): config key
            t (Callable[[str], T]): type to which the value is casted. Defaults to str.

        Returns:
            Union[T, None, str]: Value, or if not found, None
        """

        if field in self.config:
            return self.config[field]
        else:
            return None
