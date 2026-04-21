# NOTE: Don't use buildx
# TODO: Support building windows
ARG PYVER=3.14


FROM docker.io/library/python:${PYVER}-alpine AS build
ARG PYVER
RUN apk add git python3-dev build-base libffi-dev rust cargo openssl-dev
WORKDIR /sau
COPY . /sau/
# RUN pipx run bork build
RUN /usr/local/bin/pip install . --only-binary :all:


FROM docker.io/library/python:${PYVER}-alpine
ARG PYVER
COPY --from=build /usr/local/lib/python${PYVER}/site-packages /usr/local/lib/python${PYVER}/site-packages/
COPY --from=build /usr/local/bin/swiss-army-upload /usr/local/bin/sau /usr/local/bin/
