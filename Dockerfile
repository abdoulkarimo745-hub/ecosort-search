FFROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --default-timeout=100 --retries 5 -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["python", "app/main.py"]
