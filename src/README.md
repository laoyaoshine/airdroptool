# Airdrop Tool

This is an optimized tool for automating airdrop tasks, integrating Chrome multi-window management, proxy handling, Sybil defense, cloud deployment, and a graphical user interface with enhanced performance and stability.

## Installation
1. Clone this repository or create the directory structure manually.
2. Run `chmod +x setup.sh && ./setup.sh` to install dependencies and build the Docker image.

## Usage
- Create a `proxies.csv` file with proxy details (format: IP,Port).
- Start the GUI with `python src/ui/gui.py` to configure and run airdrop tasks.
- Deploy to cloud using `python src/cloud/aws_deploy.py` or `python src/cloud/gcp_deploy.py`.

## Prerequisites
- Python 3.9+
- Chrome browser
- Docker (for cloud deployment)
- AWS or Google Cloud credentials (for cloud deployment)

## License
MIT License (consult Devilflasher's original terms).