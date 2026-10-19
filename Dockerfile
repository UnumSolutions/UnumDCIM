FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS service
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home unum
ARG MODULE=inventory
COPY manage.py ./
COPY platform_core ./platform_core
COPY unum_sync ./unum_sync
COPY services/__init__.py ./services/__init__.py
COPY services/${MODULE} ./services/${MODULE}
COPY contracts ./contracts
ENV UNUM_SERVICE=${MODULE}
USER 10001
EXPOSE 8000
CMD ["gunicorn", "platform_core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "30", "--access-logfile", "-"]
