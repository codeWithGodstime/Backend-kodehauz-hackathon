import json
from typing import Dict, List

from fastapi.testclient import TestClient

from app.core.config import settings


def read_stream_events(
    client: TestClient,
    url: str,
    timeout: float = 0.5,
    iterations: int = 1,
    stream_delay: float = 0.05,
    retry_timeout: int = 50,
) -> List[Dict]:
    # Confirm stream events.
    lines = []
    settings.STREAM_RETRY_TIMEOUT = retry_timeout
    settings.STREAM_DELAY = stream_delay
    with client.stream(
        "GET",
        url,
        timeout=timeout,
        params={"iterations": iterations},
    ) as r:
        assert r.status_code == 200
        data = {}
        for line in r.iter_lines():
            if line:
                name, value = line.split(": ", 1)
                data[name] = json.loads(value) if name == "data" else value
            else:
                if data != {}:
                    lines.append(data)
                data = {}

    return lines
