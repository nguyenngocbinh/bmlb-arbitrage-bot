"""Backward-compatible launcher. Prefer ``python -m cli.main``."""
from dotenv import load_dotenv

from cli.main import main

if __name__ == "__main__":
    import asyncio
    load_dotenv()
    asyncio.run(main())
