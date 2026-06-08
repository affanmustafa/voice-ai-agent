# Python realtime voice service
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY . .

# Bind to all interfaces inside the container so the Next.js service can reach it.
ENV HOST=0.0.0.0
ENV PORT=5050

EXPOSE 5050

CMD ["python", "main.py"]
