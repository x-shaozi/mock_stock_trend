FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY --chown=10001:10001 app/ ./app/

USER 10001:10001

EXPOSE 18000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18000"]
