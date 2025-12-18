# AWS Lambda Deployment Guide

## Overview

The FastAPI application now supports AWS Lambda deployment using Mangum adapter. You can run it both locally and deploy to AWS Lambda.

## Files

- **`api_app.py`**: Core FastAPI application with all endpoints and logic
- **`app_handler.py`**: Lambda handler wrapper using Mangum + local execution support
- **`.env`**: Environment configuration including AWS region

## Local Development

### Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pydantic` - Data validation
- `mangum` - AWS Lambda/API Gateway adapter

### Run Locally

```bash
py app_handler.py
```

Or:

```bash
python app_handler.py
```

The server will start on **http://localhost:8000**

You'll see:
```
Running the FastAPI server on port 8000.
INFO - Environment variables loaded
INFO - FastAPI application initialized
INFO - Configuration loaded from ...
```

### Access API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## AWS Lambda Deployment

### Prerequisites

1. AWS CLI installed and configured
2. SAM CLI or Serverless Framework (optional but recommended)
3. AWS credentials set up

### Environment Variables

The application requires these environment variables:

```
GEMINI_API_KEY=your_gemini_api_key
DB_HOST=your_database_host
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_NAME=your_database_name
DB_PORT=5432
AWS_REGION=eu-west-1
```

### Deployment Options

#### Option 1: AWS SAM (Recommended)

Create `template.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Timeout: 30
    MemorySize: 512

Resources:
  QuestionGeneratorFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: .
      Handler: app_handler.handler
      Runtime: python3.11
      Environment:
        Variables:
          GEMINI_API_KEY: !Ref GeminiApiKey
          DB_HOST: !Ref DBHost
          DB_USER: !Ref DBUser
          DB_PASSWORD: !Ref DBPassword
          DB_NAME: !Ref DBName
          DB_PORT: !Ref DBPort
          AWS_REGION: eu-west-1
      Events:
        ApiEvent:
          Type: Api
          Properties:
            Path: /{proxy+}
            Method: ANY

Parameters:
  GeminiApiKey:
    Type: String
    NoEcho: true
  DBHost:
    Type: String
  DBUser:
    Type: String
    NoEcho: true
  DBPassword:
    Type: String
    NoEcho: true
  DBName:
    Type: String
  DBPort:
    Type: String
    Default: "5432"
```

Deploy:
```bash
sam build
sam deploy --guided
```

#### Option 2: Serverless Framework

Create `serverless.yml`:

```yaml
service: question-generator-api

provider:
  name: aws
  runtime: python3.11
  region: eu-west-1
  environment:
    GEMINI_API_KEY: ${env:GEMINI_API_KEY}
    DB_HOST: ${env:DB_HOST}
    DB_USER: ${env:DB_USER}
    DB_PASSWORD: ${env:DB_PASSWORD}
    DB_NAME: ${env:DB_NAME}
    DB_PORT: ${env:DB_PORT}
    AWS_REGION: ${env:AWS_REGION}

functions:
  api:
    handler: app_handler.handler
    timeout: 30
    memorySize: 512
    events:
      - httpApi: '*'

plugins:
  - serverless-python-requirements

custom:
  pythonRequirements:
    dockerizePip: true
```

Deploy:
```bash
serverless deploy
```

#### Option 3: Manual Lambda Deployment

1. **Create deployment package:**
```bash
pip install -r requirements.txt -t package/
cp -r src package/
cp -r config package/
cp api_app.py app_handler.py package/
cd package
zip -r ../deployment-package.zip .
```

2. **Upload to Lambda:**
- Go to AWS Lambda Console
- Create new function (Python 3.11)
- Set handler to `app_handler.handler`
- Upload `deployment-package.zip`
- Set environment variables
- Add API Gateway trigger

### Lambda Configuration

- **Runtime**: Python 3.11
- **Handler**: `app_handler.handler`
- **Timeout**: 30 seconds (adjust based on question generation time)
- **Memory**: 512 MB minimum (adjust based on usage)
- **Environment Variables**: All variables from `.env`

### API Gateway Integration

The `handler` in `app_handler.py` is configured to work with:
- API Gateway HTTP API
- API Gateway REST API
- Application Load Balancer

Mangum automatically handles the routing and request/response transformation.

## Testing

### Local Testing
```bash
python test_api.py
```

### Lambda Testing

After deployment, test with cURL:

```bash
curl -X POST https://your-api-id.execute-api.eu-west-1.amazonaws.com/generate-questions \
  -H "Content-Type: application/json" \
  -d '{
    "curriculum": "UK National Curriculum",
    "curriculum_id": 1,
    "grade": "4",
    "grade_id": 123,
    "subject": "Maths",
    "subject_id": 1,
    "chapter": "Number",
    "chapter_id": 456,
    "topic": "Addition",
    "topic_id": 789,
    "question_type": "FIB",
    "marks": 1,
    "taxonomy": "Remembering",
    "rigor_level": "Level 1",
    "number_of_questions": 1,
    "mathml": true
  }'
```

## Cold Start Optimization

The `app_handler.py` is configured with `lifespan="off"` in Mangum to reduce cold start times:

```python
handler = Mangum(app, lifespan="off")
```

This disables startup/shutdown events in Lambda which are not needed for stateless API calls.

## Logging

CloudWatch logs will show:
- Request details
- Processing steps
- Generation results
- Any errors

Access logs at: CloudWatch > Log Groups > `/aws/lambda/your-function-name`

## Troubleshooting

### Import Errors
Make sure all dependencies are in the package:
```bash
pip install -r requirements.txt -t package/
```

### Timeout Issues
Increase Lambda timeout if question generation takes longer than 30s:
- Go to Lambda function configuration
- Increase timeout to 60-90 seconds

### Memory Issues
Monitor CloudWatch metrics and increase memory if needed:
- Check "Max Memory Used" metric
- Increase to 1024 MB if consistently high

## Cost Optimization

- Use provisioned concurrency for predictable traffic
- Set appropriate timeout (don't use max if not needed)
- Monitor invocation count and duration
- Consider caching frequently requested combinations

## Security

- Store sensitive values (API keys, DB passwords) in AWS Secrets Manager
- Use IAM roles for Lambda execution
- Enable API Gateway authentication/authorization
- Use VPC if accessing private databases
