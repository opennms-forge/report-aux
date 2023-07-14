<img src="https://img.shields.io/badge/Python-3.7.4-blue"/>

# Reporting-auxiliary

Custom reporting module for trending data from OpenNMS Horizon/Meridian

NOTE: Currently only reports on `ltmVSStatName` resources from F5 load balancers.

## Requirements

Make sure the following are installed prior to Python.

* `yum install openssl-devel bzip2-devel xz-devel`

## Installation

* Go to the `/opt/` directory
* Run `git clone https://github.com/opennms-forge/report-aux` top copy the files locally
* Switch to the new `report-aux` directory
* Run`./install.sh` to install required Python libraries
* Run `sudo cp report-aux.service /etc/systemd/system/`
* Run `sudo systemctl daemon-reload`

Configuration files must be created prior to starting the service.
These are placed in the `src/ra_config` folder inside the installation directory.

* **logo.png** - Logo to place in the top right corner of PDF output
* **logo_customer.png** - Logo to place in the top center of PDF output
* **config.json** - Configuration file with connection information
  * The format for this file should be: \
    `{"url": "", "username": "", "password": ", "nodes": []}`
  * `url` is the REST API endpoint for an OpenNMS instance, such as `"http://hostname:8980/opennms/rest/"`
  * `username` and `password` to connect to the above instance for pulling metrics
  * `nodes` is an array of arrays to list the foreign source:foreign ID of nodes that make up each F5 pair. \
    `[["fs:fid","fs:fid2"], ["fs2:fid3","fs2:fid4"]]`

## Usage

The `report-aux` service can be started/stopped/enabled via `systemctl`.

Once running, the service is available at `http://hostname:8080`.
A reverse proxy can be setup to redirect traffic if HTTPS is desired.

### Optional export scheduling

If PDFs are desired on a regular basis, the command `python3 export_all.py` can be setup as a cron job to run in the `/opt/report-aux` directory and it will output PDFs for all configured pairs to the `static/pdf/` directory and a zip file to the `static/` directory.

## Updating

Updating is as simple as running a `git pull` from the install folder, rerunning the `./install.sh` script, and restarting the service.
