FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app
RUN pip install --no-cache-dir dnslib

COPY resolver.py .

EXPOSE 53/udp
CMD ["python", "resolver.py"]
