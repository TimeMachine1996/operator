FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY fluentd/ ./fluentd/

EXPOSE 8443

CMD ["python", "-m", "app.main"]