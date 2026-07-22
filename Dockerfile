FROM python:3.11-slim

LABEL org.opencontainers.image.title="datalake-acl-test" \
      org.opencontainers.image.description="Azure Data Lake ACL read test via Managed Identity"

WORKDIR /app

EXPOSE 8080
ENV PORT=8080
ENV LISTEN_HOST=0.0.0.0

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY test_azure_blob_mi.py app.py ./

CMD ["python", "app.py"]
