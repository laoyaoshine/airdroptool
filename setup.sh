#!/bin/bash

# 安装依赖
echo "Installing Python dependencies..."
pip install -r requirements.txt

# 确保 Chrome 浏览器安装（Windows/Linux 示例）
if [ "$(uname)" == "Linux" ]; then
    echo "Installing Chrome for Linux..."
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
    apt-get update -y
    apt-get install -y google-chrome-stable
elif [ "$(uname)" == "Darwin" ]; then
    echo "Installing Chrome for macOS..."
    brew install --cask google-chrome
else
    echo "Assuming Chrome is installed on Windows..."
fi

# 构建 Docker 镜像
echo "Building Docker image..."
docker build -t airdrop-tool .

# 运行 GUI（本地测试）
echo "Running Airdrop Tool GUI..."
python src/ui/gui.py

# 提示云部署选项
echo "To deploy to cloud, run:"
echo "  python src/cloud/aws_deploy.py  # for AWS"
echo "  python src/cloud/gcp_deploy.py  # for Google Cloud"