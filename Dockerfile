FROM python:3.9-slim

WORKDIR /app
COPY src/ ./src
COPY requirements.txt .

RUN pip install -r requirements.txt

# 暴露端口（可选，用于云部署）
EXPOSE 8080

CMD ["python", "src/ui/gui.py"]