FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 7860
ENV M2A_PREVIEW_PORT=7860
CMD ["python3", "run.py", "--port", "7860"]
