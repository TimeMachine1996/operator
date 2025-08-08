from fastapi import FastAPI, Body, Request
import uvicorn
from .webhook import process_admission_request
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("webhook")

app = FastAPI(title="Fluentd Sidecar Injector")

@app.get("/")
async def health():
    return {"status": "healthy"}

@app.post("/mutate")
async def mutate(request: dict = Body(...)):
    logger.info("Received admission request")
    return process_admission_request(request)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8443)