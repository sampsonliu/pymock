FROM python:3.7.4-alpine
EXPOSE 8080 80
WORKDIR /pymock
COPY pymock*.whl ./
RUN pip install pymock*.whl && rm pymock*.whl
ENTRYPOINT pymock
