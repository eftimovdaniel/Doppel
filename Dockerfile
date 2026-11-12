FROM python:3.12-slim

WORKDIR /app
COPY backend /app/backend
COPY frontend /app/frontend
WORKDIR /app/backend

ENV PORT=8080
ENV HOST=0.0.0.0
ENV DOPPEL_DB=/data/doppel.db

EXPOSE 8080
CMD ["python3", "-u", "main.py"]
