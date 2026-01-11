from typing import Union, TypeVar, Callable, List, Any
import yaml
from pathlib import Path


T = TypeVar("T")


class ConfigReader:
    """YAML Config reader class"""

    def __init__(self, config_file: str):
        if Path(config_file).exists():
            with open(config_file, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
            # print(f"Load config: {config_file}")
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
