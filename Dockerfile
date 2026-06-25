FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m nltk.downloader wordnet omw-1.4 punkt averaged_perceptron_tagger_eng

COPY . .

ENV LOAD_MODELS=0
ENV OBSERVER_MODEL=gpt2
ENV PERFORMER_MODEL=gpt2-medium

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
