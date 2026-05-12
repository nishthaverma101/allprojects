FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY app.py .
COPY in-airports.csv .

EXPOSE 5000

# 4 workers × 4 threads = 16 concurrent request slots
CMD ["gunicorn", "-w", "4", "--threads", "4", "-b", "0.0.0.0:5000", "--timeout", "30", "app:app"]