FROM python:3.10-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 SETTINGS_SKIP_DOTENV=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
