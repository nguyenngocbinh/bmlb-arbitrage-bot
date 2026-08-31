"""Backward-compatible launcher. Prefer ``python -m cli.main``."""
from cli.main import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
