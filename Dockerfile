FROM public.ecr.aws/docker/library/python:3.12

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    ghostscript \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
