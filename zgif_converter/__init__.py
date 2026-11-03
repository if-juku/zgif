"""Convert videos to the observed ZGIF v1 archive format."""

from .converter import ConversionError, Options, convert

__all__ = ["ConversionError", "Options", "convert"]
