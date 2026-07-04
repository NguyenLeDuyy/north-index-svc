FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal; requests/markdownify are pure-python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scraper.py state.py vector_store.py main.py ./

# Persist state + scraped articles across runs by mounting a volume here:
#   docker run -v $(pwd)/data:/app/data -e GEMINI_API_KEY=... <image>
VOLUME ["/app/data", "/app/state"]

ENTRYPOINT ["python", "main.py"]
