FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRAUD_AUTO_TRAIN=1

ARG TRAIN_ON_BUILD=0

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN if [ "$TRAIN_ON_BUILD" = "1" ]; then python model/train.py; fi

EXPOSE 8000

CMD ["uvicorn", "api.fraud_api:app", "--host", "0.0.0.0", "--port", "8000"]
