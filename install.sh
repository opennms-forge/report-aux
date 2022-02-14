# @author Mark Mahacek <mmahacek@opennms.com>

echo Setting up Python virtual environment to isolate from other Python apps
python3 -m venv venv
source venv/bin/activate
echo Upgrading Python pip to latest version
pip3 install --upgrade pip wheel
echo Installing Python dependencies
pip3 install -r requirements.txt
echo Install script complete
