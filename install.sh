#!env bash
# @author Mark Mahacek <mmahacek@opennms.com>

python3 -m venv venv
source venv/bin/activate
pip3 install --upgrade pip wheel
pip3 install -r requirements.txt
