FROM python:3.9

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY . /code

# Run ingest at build time so chroma_db is baked into the image
# (chroma_db is gitignored so must be built from the PDF)
RUN python ingest.py knowledge_base/BNF80.pdf

# HF Spaces requires port 7860
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7860"]