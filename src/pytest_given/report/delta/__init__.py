"""Rendering a delta: the page that sets two reports side by side, and its
sinks."""

from .sinks import DeltaSinkConfig, emit_delta_sinks

__all__ = ['DeltaSinkConfig', 'emit_delta_sinks']
