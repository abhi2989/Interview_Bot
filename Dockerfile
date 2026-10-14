FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy
RUN apt-get update && apt-get install -y --no-install-recommends \
    pulseaudio pulseaudio-utils xvfb && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
