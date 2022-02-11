python3 -m venv venv
source venv/bin/activate
pip3 install --upgrade pip wheel
pip3 install -r requirements.txt
sudo cp report-aux.service /etc/systemd/system/
sudo systemctl daemon-reload
