# Use the official PostgreSQL image from the Docker Hub
FROM postgres:latest

# Define build-time variables
ARG POSTGRES_DB
ARG POSTGRES_USER
ARG POSTGRES_PASSWORD
ARG CONTAINER_NAME
ARG POSTGRES_PORT
ARG POSTGRES_HOST

# Set environment variables that the postgres image uses
ENV POSTGRES_DB=${POSTGRES_DB}
ENV POSTGRES_USER=${POSTGRES_USER}
ENV POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
ENV CONTAINER_NAME=${CONTAINER_NAME}
ENV POSTGRES_PORT=${POSTGRES_PORT}
ENV POSTGRES_HOST=${POSTGRES_HOST}
# # Install necessary packages for downloading and decompressing the face detector model
# USER root
# RUN apt-get update && \
#     apt-get install -y wget bzip2 && \
#     apt-get clean && \
#     rm -rf /var/lib/apt/lists/*

# # Download the dlib CNN face detection model and extract it
# WORKDIR /appdata
# RUN wget http://dlib.net/files/mmod_human_face_detector.dat.bz2 && \
#     bzip2 -d mmod_human_face_detector.dat.bz2

# # Switch back to the postgres user for safety
# USER postgres

# For example, copying initialization scripts into the Docker image
COPY ./init.sql /docker-entrypoint-initdb.d/

# This command will be executed when the container starts up
CMD ["postgres"]