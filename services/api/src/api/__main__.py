import os

import uvicorn

from shared.config import load_dotenv


def entrypoint() -> None:
    load_dotenv()
    host = os.environ.get("API_HOST", "127.0.0.1")
    port = int(os.environ.get("API_PORT", "8000"))
    reload = os.environ.get("API_RELOAD", "0") == "1"
    uvicorn.run("api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    entrypoint()
