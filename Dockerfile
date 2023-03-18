FROM pytorch/pytorch:latest

COPY ./requirements.txt ./

RUN python3 -m ensurepip --upgrade

RUN pip install --upgrade pip wheel
RUN pip install -r requirements.txt

ENV PYTHONPATH=.

WORKDIR .