from dotenv import load_dotenv

# Must run before backend.api is imported (uvicorn does that lazily from the
# "backend.api:app" string below) - backend/agents.py, backend/thinkst.py,
# and backend/github_canary.py all read their config as module-level
# os.environ.get(...) constants at import time.
load_dotenv()

import uvicorn


def main():
    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
