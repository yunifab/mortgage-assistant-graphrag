"""Small client for the RDFox REST API (see docs/RDFOX_SETUP.md for starting the server).

Every case check uses its own short-lived datastore:
    create -> load ontology + rules + case facts -> query findings -> delete
That keeps checks independent of each other (no leftovers) and is fast for a small ontology.
"""

import os
import uuid
from contextlib import contextmanager

import httpx

ENDPOINT = os.getenv("RDFOX_ENDPOINT", "http://localhost:12110")
AUTH = (os.getenv("RDFOX_ROLE", "admin"), os.getenv("RDFOX_PASSWORD", "admin"))


class RDFoxError(RuntimeError):
    pass


def _client() -> httpx.Client:
    return httpx.Client(base_url=ENDPOINT, auth=AUTH, timeout=30)


def is_available() -> bool:
    try:
        with _client() as c:
            return c.get("/datastores").status_code == 200
    except httpx.HTTPError:
        return False


class Datastore:
    def __init__(self, client: httpx.Client, name: str):
        self.c, self.name = client, name

    def _check(self, r: httpx.Response, what: str) -> httpx.Response:
        if r.status_code >= 400:
            raise RDFoxError(f"{what} failed ({r.status_code}): {r.text[:1500]}")
        return r

    def load_turtle(self, text: str) -> None:
        self._check(self.c.post(f"/datastores/{self.name}/content", content=text.encode("utf-8"),
                                headers={"Content-Type": "text/turtle"}), "loading Turtle")

    def load_datalog(self, text: str) -> None:
        r = self._check(self.c.post(f"/datastores/{self.name}/content", content=text.encode("utf-8"),
                                    headers={"Content-Type": "application/x.datalog"}), "loading rules")
        if "#errors = 0" not in r.text:
            raise RDFoxError("rule errors:\n" + r.text[:3000])

    def select(self, sparql: str) -> list[dict]:
        """SPARQL SELECT -> list of {variable: value as string} (RDF terms without < > or quotes)."""
        r = self._check(self.c.post(f"/datastores/{self.name}/sparql", data={"query": sparql},
                                    headers={"Accept": "application/sparql-results+json"}), "query")
        rows = []
        for b in r.json()["results"]["bindings"]:
            rows.append({k: v["value"] for k, v in b.items()})
        return rows


@contextmanager
def temporary_datastore():
    name = f"case-{uuid.uuid4().hex[:10]}"
    with _client() as c:
        r = c.post(f"/datastores/{name}")
        if r.status_code >= 400:
            raise RDFoxError(f"creating datastore failed ({r.status_code}): {r.text[:300]}")
        try:
            yield Datastore(c, name)
        finally:
            c.delete(f"/datastores/{name}")
