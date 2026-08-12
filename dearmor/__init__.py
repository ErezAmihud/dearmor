"""dearmor -- recover the original bytecode of pyarmor obfuscated files."""

from .__main__ import dearmor_main, deobfuscate_file, main_cli

__all__ = ["deobfuscate_file", "dearmor_main", "main_cli"]
