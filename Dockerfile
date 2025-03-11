FROM python:3.12.9-slim AS builder

RUN apt-get -y update && \
    apt-get -y install curl && \
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

ARG SESSIONS_PROVIDER
ARG USERS_PROVIDER
RUN \
    if [ -z "$SESSIONS_PROVIDER" ]; then echo "\n\nERROR: build arg SESSIONS_PROVIDER is not set\n\n"; exit 1; \
    else echo "building with SESSIONS_PROVIDER '$SESSIONS_PROVIDER'"; fi; \
    if [ -z "$USERS_PROVIDER" ]; then echo "\n\nERROR: build arg USERS_PROVIDER is not set\n\n"; exit 1; \
    else echo "building with USERS_PROVIDER '$USERS_PROVIDER'"; fi;

# TODO: $SESSIONS_PROVIDER and $USERS_PROVIDER .to_lower() for just in case

COPY ./pyproject.toml ./

ENV VIRTUAL_ENV=/app/venv
ARG UV_CACHE_DIR=/opt/uv_cache
RUN --mount=type=cache,target=${UV_CACHE_DIR} \
    PYTHONUNBUFFERED=1 \
    uv venv ${VIRTUAL_ENV} && \
    uv sync \
        --active \
        --no-install-project \
        --no-default-groups \
        --group sessions-${SESSIONS_PROVIDER} \
        --group users-${USERS_PROVIDER}



FROM python:3.12.9-slim

ARG APP_DIR=/app
WORKDIR ${APP_DIR}

COPY --from=builder /app/venv ./venv
COPY ./src ./src
COPY ./protos ./src/protos

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="${APP_DIR}/venv/bin:$PATH"
ENV PYTHONPATH="${APP_DIR}/src"

ENV PORT_HTTP=80
EXPOSE ${PORT_HTTP}
ENV PORT_GRPC=50051
EXPOSE ${PORT_GRPC}

ENTRYPOINT [ "python", "./src/main.py" ]
# CMD ["tail", "-f", "/dev/null"]
