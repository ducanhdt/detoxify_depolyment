import os
import logging
import json
import time
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from openai import OpenAI

# Import the logging setup from the new logging.py file
from logging_handle import setup_cloud_logging, flush_cloud_loggers

# Assuming these are available in your environment or project
from delete_baseline import DetoxificationBaseline as delete_baseline
from utils import get_messages, parse_detoxified_output

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
VLLM_API_BASE_URL = os.getenv("vLLM_API", "localhost")
VLLM_OPENAI_COMPLETIONS_URL = f"http://{VLLM_API_BASE_URL}:8000/v1/chat/completions"
VLLM_METRICS_URL = f"http://{VLLM_API_BASE_URL}:8000/metrics"

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "your-gcp-project-id")

# Log names for Google Cloud Logging
INFERENCE_LOG_NAME = "llm-detox-inference-logs"
VLLM_METRICS_LOG_NAME = "vllm-metrics-snapshot-logs"

# --- Setup Cloud Logging ---
# Call the setup function from logging_config.py
inference_logger = setup_cloud_logging(
    gcp_project_id=GCP_PROJECT_ID,
    inference_log_name=INFERENCE_LOG_NAME,
    metrics_log_name=VLLM_METRICS_LOG_NAME
)




class TextSanitizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path == "/detoxify":
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid JSON format in request body."}
                )

            if not isinstance(body.get("text"), str) or not isinstance(body.get("language_id"), str):
                # Debug logging to understand what we're receiving
                text_value = body.get("text")
                language_id_value = body.get("language_id")
                
                inference_logger.warning(
                    "Invalid request format",
                    extra={"json_payload": {
                        "request_id": getattr(request.state, 'request_id', 'unknown'), 
                        "received_body": body,
                        "text_type": type(text_value).__name__,
                        "text_value": text_value,
                        "language_id_type": type(language_id_value).__name__,
                        "language_id_value": language_id_value
                    }}
                )
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": "Invalid request format.", 
                        "error": f"text must be string (got {type(text_value).__name__}), language_id must be string (got {type(language_id_value).__name__})"
                    }
                )

            forbidden_keywords = ["prompt", "secret", "token", "password"]
            if any(keyword in body.get("text", "").lower() for keyword in forbidden_keywords):
                inference_logger.warning(
                    "Forbidden keyword detected in request",
                    extra={"json_payload": {"request_id": getattr(request.state, 'request_id', 'unknown'), "text_preview": body.get("text", "")[:100]}}
                )
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Query contains forbidden content."}
                )

            if len(body.get("text", "")) > 500:
                inference_logger.warning(
                    "Query too long",
                    extra={"json_payload": {"request_id": getattr(request.state, 'request_id', 'unknown'), "text_length": len(body.get("text", ""))}}
                )
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Query is too long."}
                )

        response = await call_next(request)
        return response

# Use lifespan event handler for app startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    global detoxify_baseline
    global openai_client

    # Initialize detoxification baseline
    detoxify_baseline = delete_baseline()

    # Initialize OpenAI client for vLLM
    openai_api_key = os.getenv('vLLM_KEY',"NONE")
    openai_client = OpenAI(
        api_key=openai_api_key,
        base_url=f"http://{VLLM_API_BASE_URL}:8000/v1",
    )

    yield

    logging.info("FastAPI application shutting down. Flushing logs...")
    flush_cloud_loggers([inference_logger]) # Use the new flush function
    logging.info("Logs flushed. FastAPI application shut down.")

# Define the app with the lifespan handler and middlewares
app = FastAPI(lifespan=lifespan)
app.add_middleware(TextSanitizationMiddleware)

# Schema for detoxification request
class DetoxificationRequest(BaseModel):
    text: str
    language_id: str

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

# Detoxification endpoint
@app.post("/detoxify")
async def detoxify(request: DetoxificationRequest):
    start_time = time.perf_counter()
    input_text = request.text.strip()
    language_id = request.language_id.lower()
    request_id = os.urandom(8).hex()
    try:
        messages = get_messages(input_text, language_id)
        
        if language_id in ['fr','it','hin','ja','tt','he']:
            model_name = "unseen-language"
        else:
            model_name = "seen-language"

        response = openai_client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=500,
            temperature=1
        )
        
        output_text = response.choices[0].message.content
        parsed_output = parse_detoxified_output(output_text, language_id)

        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0
        total_tokens = response.usage.total_tokens if response.usage else 0
        model_id_from_response = response.model

        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000

        result_dict = {"input_text": input_text,
                    "language_id": language_id,
                    "model_used": model_name,
                    "actual_model_id": model_id_from_response,
                    "detoxified_text": parsed_output['neutral_text'],
                    "toxicity_terms_detected": parsed_output['toxic_words'],
                    "latency_ms": latency_ms,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                }

        inference_logger.info(
            "Detoxification Inference Completed",
            extra={
                "json_payload": {
                    "request_id": request_id,
                    **result_dict,
                }
            }
        )

        return JSONResponse(
            content={
                "status": "success",
                "data": result_dict
            },
            status_code=200
        )
    except Exception as e:
        inference_logger.error(
            f"Detoxification error for request_id: {request_id}",
            exc_info=True,
            extra={
                "json_payload": {
                    "request_id": request_id,
                    "input_text": input_text,
                    "language_id": language_id,
                    "error_type": e.__class__.__name__,
                    "error_message": str(e),
                    "model_used": model_name if 'model_name' in locals() else 'unknown',
                }
            }
        )
        raise HTTPException(status_code=503, detail="Service is not available now. Please try again later.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
