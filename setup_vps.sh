#!/usr/bin/env bash
# ==============================================================================
# Script for automated setup and configuration of a Discord tool / 24/7 voice channel presence on a Linux VPS
# ==============================================================================

set -e

# Display colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}======================================================================${NC}"
echo -e "${CYAN}       AUTO SETUP FOR DISCORD TOOL / 24/7 VOICE CHANNEL ON LINUX VPS       ${NC}"
echo -e "${CYAN}======================================================================${NC}"

# Safely determine root/sudo privileges
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
if command -v sudo &>/dev/null; then
SUDO="sudo"
else
echo -e "${RED}Please run this script as root or install sudo!${NC}"
exit 1
fi
fi

# 1. Update the system and check the Python version
echo -e "\n${YELLOW}[1/4] Updating system and checking Python version...${NC}"
PYTHON_CMD="python3"

if command -v apt-get &>/dev/null; then 
export DEBIAN_FRONTEND=noninteractive 
$SUDO apt-get update -y 
$SUDO apt-get install -y python3 python3-pip python3-venv git tmux curl build-essential libffi-dev software-properties-common 

# Check current Python version 
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0) 
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo 0) 

# Discord Voice mandates new DAVE protocol (requires discord.py-self 2.1.0+ and Python >= 3.10) 
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then 
echo -e "${YELLOW}Detecting old Python $PY_MAJOR.$PY_MINOR. Automatically upgrading to Python 3.11...${NC}" 
$SUDO add-apt-repository -y ppa:deadsnakes/ppa 
$SUDO apt-get update -y 
$SUDO apt-get install -y python3.11 python3.11-venv python3.11-dev 
PYTHON_CMD="python3.11" 
else. else 
PYTHON_CMD="python3" 
fi
elif command -v yum &>/dev/null; then
$SUDO yum update -y
$SUDO yum install -y python3 python3-pip git tmux curl gcc libffi-devel
PYTHON_CMD="python3"
fi

echo -e "${GREEN}Using interpreter: $PYTHON_CMD ($($PYTHON_CMD --version))${NC}"

# 2. Prepare the source code directory
echo -e "\n${YELLOW}[2/4] Checking source code...${NC}"
REPO_DIR="$HOME/discord-bot-auto-quest"

if [ -d "$REPO_DIR/.git" ]; then
echo -e "${GREEN}Repository directory found; pulling the latest updates...${NC}"
cd "$REPO_DIR"
git fetch origin
git reset --hard origin/main
else
echo -e "${GREEN}Cloning source code from GitHub to $REPO_DIR...${NC}"
git clone https://github.com/Mhna3112/discord-bot-auto-quest.git "$REPO_DIR"
cd "$REPO_DIR"
fi

# 3. Create Python virtual environment (venv) & install dependencies
echo -e "\n${YELLOW}[3/4] Setting up Python virtual environment and dependencies...${NC}"

# Always refresh the venv if it uses a Python version < 3.10
if [ -d "venv" ]; then
VENV_PY_MINOR=$(./venv/bin/python3 -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo 0)
if [ "$VENV_PY_MINOR" -lt 10 ]; then
echo -e "${YELLOW}Removing old Python virtual environment ($VENV_PY_MINOR) to create a new one using $PYTHON_CMD...${NC}"
rm -rf venv
fi
fi

if [ ! -d "venv" ]; then then
$PYTHON_CMD -m venv venv
fi

./venv/bin/pip install --upgrade pip setuptools wheel
./venv/bin/pip install -r requirements.txt

# 4. Installation Complete
echo -e "\n${GREEN}======================================================================${NC}"
echo -e "${GREEN}                   INSTALLATION SUCCESSFUL ON VPS!                   ${NC}"
echo -e "${GREEN}======================================================================${NC}"
echo -e "\n${CYAN}To keep the voice tool running 24/7 even after closing Termius, run:${NC}"
echo -e "  ${YELLOW}tmux new -s voice${NC}             # Open a tmux background session"
echo -e "  ${YELLOW}cd ~/discord-bot-auto-quest${NC}   # Navigate to the bot directory"
echo -e "  ${YELLOW}source venv/bin/activate${NC}      # Activate the Python environment"
echo -e "  ${YELLOW}python treo_voice.py${NC}          # Start the voice tool"
echo -e "\n${CYAN}Important tmux shortcuts:${NC}"
echo -e "  - Detach from the session (keep the tool running): Press ${YELLOW}Ctrl + B${NC}, then press ${YELLOW}D${NC}"
echo -e "  - Reattach to the running session: Use the command ${YELLOW}tmux attach -t voice${NC}"
echo -e "======================================================================\n"

# Ask the user if they want to run the tool immediately
read -p "👉 Would you like to run the Voice tool now? (y/n): " RUN_NOW
if [[ "$RUN_NOW" =~ ^[Yy]$ ]]; then
./venv/bin/python treo_voice.py
fi