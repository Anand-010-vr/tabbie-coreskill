from fastapi import FastAPI
from mangum import Mangum
import uvicorn

# Import the FastAPI app from api_app
from api_app import app as fastapi_app

app: FastAPI = fastapi_app

# AWS Lambda handler for the FastAPI application
# Configure lifespan off to reduce cold start overhead in Lambda
handler = Mangum(app, lifespan="off")

if __name__ == "__main__":
    # Run locally with uvicorn if executed directly
    port = 8000
    print(f"Running the FastAPI server on port {port}.")
    uvicorn.run(app, host="0.0.0.0", port=port)
