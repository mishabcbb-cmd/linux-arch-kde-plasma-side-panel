"""A2A Hub MCP Server — объединяет MCP протокол с A2A Hub.

MCP для инструментов/ресурсов, A2A для агент-агент коммуникации.
"""

from .server import A2AMCPServer

__all__ = ["A2AMCPServer"]
