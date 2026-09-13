import os
from dotenv import load_dotenv

# Must run before backend.api is imported (uvicorn does that lazily from the
# "backend.api:app" string below) - backend/agents.py, backend/thinkst.py,
# and backend/github_canary.py all read their config as module-level
# os.environ.get(...) constants at import time.
load_dotenv()

import uvicorn


def main():
    # Tells backend/api.py's startup hook it's safe to reconcile
    # dns-resolver/zones.json + log-monitor/endpoints.json against the
    # real, in-memory data.canary_instances (see reconcile_canary_registrations's
    # docstring) - set here, not in backend/api.py itself, so constructing
    # the FastAPI app for testing (TestClient(app), with no equivalent "this
    # is a real server" signal) never touches those real on-disk files.
    # Inherited by uvicorn's --reload worker subprocess too, since it's set
    # in this process's environment before uvicorn.run spawns it.
    os.environ["CANARYNET_RECONCILE_ON_STARTUP"] = "1"
    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
