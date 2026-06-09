"""Tests for the /api/extract endpoint (app/routers/extraction.py + app/main.py)."""


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_extract_valid_image_returns_200(client, make_text_image):
    png = make_text_image("Endpoint Test")
    r = client.post("/api/extract", files={"file": ("test.png", png, "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert {"text", "words", "metadata"} <= body.keys()
    assert body["metadata"]["engine"] == "tesseract"
    assert len(body["words"]) > 0


def test_extract_rejects_plain_text_file(client):
    r = client.post(
        "/api/extract", files={"file": ("note.txt", b"just plain text", "text/plain")}
    )
    assert r.status_code == 400
    assert r.json()["error_type"] == "unrecognized_file_type"


def test_extract_rejects_empty_file(client):
    r = client.post("/api/extract", files={"file": ("empty.png", b"", "image/png")})
    assert r.status_code == 400
    assert r.json()["error_type"] == "empty_file"


def test_extract_rejects_disguised_script(client):
    script = b"#!/bin/bash\nrm -rf /\n"
    r = client.post("/api/extract", files={"file": ("evil.png", script, "image/png")})
    assert r.status_code == 400
    assert r.json()["error_type"] == "unrecognized_file_type"
