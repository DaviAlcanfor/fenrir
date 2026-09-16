# fenrir API server
FROM python:3.13-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir uv && uv pip install --system --no-cache -e .

FROM python:3.13-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/fenrir ./src/fenrir
COPY src/fenrir/prompts ./src/fenrir/prompts
COPY src/fenrir/skills ./src/fenrir/skills
ENV PYTHONPATH=/app/src
EXPOSE 8000
ENTRYPOINT ["fenrir-api"]