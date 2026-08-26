# Image that runs the pipeline end to end (Step 7).
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY sql/ ./sql/
COPY config/ ./config/
CMD ["python", "-m", "src.pipeline"]
