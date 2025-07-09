from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
from openai import OpenAI

from delete_baseline import DetoxificationBaseline as delete_baseline
from utils import get_messages, parse_detoxified_output

# Load environment variables from .env file
load_dotenv()


# Configure logging to log to a file
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),  # Log to a file named 'app.log'
        logging.StreamHandler()          # Also log to the console
    ]
)

# Middleware to sanitize text queries
class TextSanitizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path == "/detoxify":
            body = await request.json()

            # Check for forbidden keywords
            forbidden_keywords = ["prompt", "secret", "token", "password"]
            if any(keyword in body.get("text", "").lower() for keyword in forbidden_keywords):
                raise HTTPException(status_code=400, detail="Query contains forbidden content.")

            # Limit the length of the input
            if len(body.get("text", "")) > 500:
                raise HTTPException(status_code=400, detail="Query is too long.")

            # Validate the structure of the request body
            if not isinstance(body.get("text"), str) or not isinstance(body.get("language_id"), str):
                raise HTTPException(status_code=400, detail="Invalid request format.")

        return await call_next(request)

# Use lifespan event handler for app startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    global detoxify_baseline
    global client
    detoxify_baseline = delete_baseline()
    openai_api_base = f"http://{os.getenv("vLLM_API")}:8000/v1"
    openai_api_key = os.getenv('vLLM_KEY',"NONE")
    client = OpenAI(
    # defaults to os.environ.get("OPENAI_API_KEY")
    api_key=openai_api_key,
    base_url=openai_api_base,
    )
    yield

# Define the app with the lifespan handler
app = FastAPI(lifespan=lifespan)

# Schema for detoxification request
class DetoxificationRequest(BaseModel):
    text: str
    language_id: str

# Detoxification endpoint
@app.post("/detoxify")
async def detoxify(request: DetoxificationRequest):
    try:
        language_id = request.language_id.lower()
        input_text = request.text.strip()
        messages = get_messages(input_text, language_id)
        if language_id in ['fr','it','hin','ja','tt','he']:
            model = "unseen-language"
        else:
            model = "seen-language"
        # Prepare the payload for the OpenAI API request
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=500,
            temperature=1
        )
        output_text = response.choices[0].message.content
        parsed_output = parse_detoxified_output(output_text, language_id)
        # toxicity_terms = detoxify_baseline.find_toxic_terms(text=request.text, language=request.language_id)
        return JSONResponse(
            content={
                "status": "success",
                "data": {
                    "text": input_text,
                    "language_id": language_id,
                    "detoxified_text": parsed_output['neutral_text'],
                    "toxicity_terms": parsed_output['toxic_words'],
                }
            },
            status_code=200
        )
    except Exception as e:
        logging.error(f"Detoxification error: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Service is not available now. Please try again later.")

# Run the application on a different port
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)