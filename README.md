# Airdrop Tool

This is an optimized tool for automating airdrop tasks, integrating Chrome multi-window management, proxy handling, Sybil defense, cloud deployment, and a graphical user interface with enhanced performance, stability, and security.

## Features
- **Multi-Instance Support**: Run multiple Chrome instances concurrently for airdrop tasks.
- **Proxy Management**: Batch import, real-time monitoring, and quick switching of proxies.
- **Sybil Defense**: Prevent detection by simulating natural user behavior with randomized delays and limits.
- **Automation**: Automate interactions with airdrop websites, including form filling, wallet signing, and DeFi tasks.
- **Cloud Deployment**: Support for AWS ECS and Google Cloud Run with auto-scaling.
- **User Interface**: Intuitive GUI for non-technical users to configure and monitor tasks.

## Installation
1. Clone this repository or create the directory structure manually.
2. Ensure Python 3.9+, Chrome browser, and Docker are installed.
3. Run `chmod +x setup.sh && ./setup.sh` to install dependencies, build the Docker image, and launch the GUI.

## Usage
- Create a `proxies.csv` file with proxy details (format: IP,Port).
- Start the GUI with `python src/ui/gui.py` to configure and run airdrop tasks (specify the number of instances via the GUI).
- Deploy to cloud using `python src/cloud/aws_deploy.py` (for AWS) or `python src/cloud/gcp_deploy.py` (for Google Cloud).

## Prerequisites
- Python 3.9+
- Chrome browser
- Docker (for cloud deployment)
- AWS or Google Cloud credentials (for cloud deployment)

## Configuration
- Replace placeholders in the code (e.g., `your_private_key`, `your-project`) with actual values.
- Use a hardware wallet or secure storage for private keys to ensure security.

## License
MIT License (consult Devilflasher's original terms).
