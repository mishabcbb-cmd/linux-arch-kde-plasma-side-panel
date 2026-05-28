#!/usr/bin/env python3
"""A2A Hub — точка входа для запуска сервера."""

import argparse
import logging
import os
import sys

# Добавить родительскую директорию a2a_hub в path для импорта как пакета
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="A2A Hub Server")
    parser.add_argument(
        "--config", "-c",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "agents.yaml"),
        help="Path to agents config YAML",
    )
    parser.add_argument("--host", default=None, help="Override host")
    parser.add_argument("--port", type=int, default=None, help="Override port")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger("a2a_hub")

    try:
        import yaml
        import httpx
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Install: pip install pyyaml httpx")
        sys.exit(1)

    # Импортировать как пакет a2a_hub
    from a2a_hub.server.hub_server import A2AHubServer

    hub = A2AHubServer(args.config)

    if args.host:
        hub.config.host = args.host
    if args.port:
        hub.config.port = args.port

    logger.info(f"Starting A2A Hub with config: {args.config}")
    hub.start()


if __name__ == "__main__":
    main()
