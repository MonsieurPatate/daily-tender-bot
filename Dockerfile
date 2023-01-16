FROM python:3.11.1-alpine3.16

WORKDIR /bot

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY app ./app
COPY poetry.lock pyproject.toml ./

RUN python3 -m pip install poetry

RUN poetry config virtualenvs.create false
RUN poetry env use system && poetry install

CMD ["python3", "/bot/app/main.py"]