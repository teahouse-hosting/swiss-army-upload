# TODO: Support building windows
ARG PYVER=3.14


FROM docker.io/library/python:${PYVER}-alpine AS build
ARG PYVER
RUN --mount=type=cache,id=apk,target=/var/cache apk add git poetry
WORKDIR /sau
COPY . /sau
RUN poetry build
RUN --mount=type=cache,id=pip,dst=/root/.cache/pip /usr/local/bin/pip install ./dist/swiss_army_upload-*.whl


FROM docker.io/library/python:${PYVER}-alpine
ARG PYVER
COPY --from=build /usr/local/lib/python${PYVER}/site-packages /usr/local/lib/python${PYVER}/site-packages
COPY --from=build /usr/local/bin/swiss-army-upload /usr/local/bin/sau /usr/local/bin
