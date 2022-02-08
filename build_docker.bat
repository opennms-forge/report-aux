docker build -t report-aux:latest .
docker run -d -p 5000:5000 -v ${PWD}/src/ra_config:/app/ra_config report-aux
