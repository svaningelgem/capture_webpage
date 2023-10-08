import re
from functools import cached_property
from pathlib import Path
from typing import Self

import yaml
from pydantic import Field, constr, field_validator
from pydantic.dataclasses import dataclass

HttpURL = constr(strip_whitespace=True, min_length=1, pattern='^https?://.+$')
String = constr(strip_whitespace=True, min_length=1)
Email = constr(strip_whitespace=True, min_length=1, pattern=r'^.+@.+\..+$')


__all__ = ["EmailConfig", "Config", "SiteConfig"]


@dataclass
class EmailConfig:
    sender: Email
    host: String
    port: int = 0
    has_ssl: bool = False
    username: String | None = None
    password: String | None = None

    @classmethod
    def load(cls, data: str | Path, *, encoding: str = "utf8") -> Self:
        data = Path(data).read_text(encoding=encoding)

        return cls(**yaml.safe_load(data))


@dataclass
class SiteConfig:
    url: HttpURL
    css: String
    email: Email
    unique_name: String = Field(default="", init_var=False)

    @cached_property
    def _cache(self) -> Path:
        cache_dir = Path(__file__).parent / '.cache'
        cache_dir.mkdir(mode=0o0700, parents=True, exist_ok=True)
        return cache_dir / f"{self.unique_name}.txt"

    @cached_property
    def last_text(self) -> str | None:
        try:
            return self._cache.read_text(encoding="utf8")
        except FileNotFoundError:
            return None


@dataclass
class Config:
    sites: dict[str, SiteConfig]

    @field_validator("sites")
    def set_unique_name(cls, sites: dict[str, SiteConfig]) -> dict:
        for key, value in sites.items():
            value.unique_name = re.sub("[^-_ a-z0-9.]", "", key, flags=re.IGNORECASE).strip('. \r\n\t')
        return sites

    @classmethod
    def load(cls, data: str | Path, *, encoding: str = "utf8") -> Self:
        data = Path(data).read_text(encoding=encoding)

        return cls(sites=yaml.safe_load(data))
