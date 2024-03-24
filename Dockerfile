FROM python:3-alpine as builder

# prepare venv
RUN mkdir -p /opt/app/venv
ADD requirements.txt /opt/app/requirements.txt
WORKDIR /opt/app
RUN python3 -m venv /opt/app/venv && \
    source /opt/app/venv/bin/activate && \
    pip3 install -r requirements.txt

# prepare app
RUN mkdir -p /opt/app/src/hilinkapi
ADD app.py /opt/app/src/
ADD hilinkapi/HiLinkAPI.py /opt/app/src/hilinkapi



FROM python:3-alpine

WORKDIR /opt/app
ENV PATH="/opt/app/venv/bin:$PATH"
COPY --from=builder /opt/app/venv /opt/app/venv
COPY --from=builder /opt/app/src /opt/app

ENTRYPOINT ["python3", "app.py"]
