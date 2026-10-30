FROM python:3.11-slim
WORKDIR /app
# Install deps first (layer-cached even when app code changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Then copy the project (weights included per license; .dockerignore excludes secrets/caches)
COPY . .
EXPOSE 7860
ENV M2A_PREVIEW_PORT=7860
CMD ["python3", "run.py", "--port", "7860"]
