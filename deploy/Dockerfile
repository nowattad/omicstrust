FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMICSTRUST_HOME=/data/omicstrust

WORKDIR /app

COPY pyproject.toml README.md requirements.txt /app/
COPY omicstrust /app/omicstrust
COPY configs /app/configs

RUN python -m pip install --no-cache-dir -e ".[api,reports]"

EXPOSE 8000

CMD ["omicstrust", "serve", "--host", "0.0.0.0", "--port", "8000", "--results-root", "/data/omicstrust/platform"]
