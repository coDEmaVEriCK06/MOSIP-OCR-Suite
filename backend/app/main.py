from fastapi import FastAPI

app = FastAPI(title="MOSIP OCR Suite")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
