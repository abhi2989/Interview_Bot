FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Indian
RUN apt-get update && apt-get install -y --no-install-recommends \
    pulseaudio pulseaudio-utils xvfb x11vnc novnc websockify openbox \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
