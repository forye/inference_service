FROM python:3.8-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "app.main"]

#EXPOSE 5000
#ENV NAME World
#CMD ["python", "app/main.py"]
#docker build -t my-flask-app .
#docker run -p 5000:5000 my-flask-app
