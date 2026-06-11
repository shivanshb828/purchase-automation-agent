"""
Entry point for SmartCart — orchestrates the full 3-feature purchase automation flow.
"""
# TODO: Wire orchestrator and add Rich console entry point

import asyncio
from utils.logger import get_logger

log = get_logger(__name__)


async def main() -> None:
    log.info("SmartCart starting up...")
    # TODO: Parse CLI args or prompt user for request, then call orchestrator


if __name__ == "__main__":
    asyncio.run(main())
