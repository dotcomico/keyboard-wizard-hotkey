"""Thin adapters over the Win32 APIs used by the pipeline.

Each module creates its own ``ctypes.WinDLL("user32")`` so its argtypes
cannot clash with pystray's, which sets them on ``ctypes.windll.user32``.
"""
