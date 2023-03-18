FROM pytorch/manylinux-cuda116

COPY ./requirements.txt ./
COPY ./requirements-torch.txt ./

RUN python3 -m ensurepip --upgrade

RUN pip install --upgrade pip wheel
RUN pip install -r requirements.txt
RUN pip install -r requirements-torch.txt

ENV PYTHONPATH=.

WORKDIR .