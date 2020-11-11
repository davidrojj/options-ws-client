# Echo commands
set -v
sudo su -

# [START getting_started_gce_startup_script]
# Install Stackdriver logging agent
curl -sSO https://dl.google.com/cloudagents/install-logging-agent.sh
bash install-logging-agent.sh

# Install or update needed software
apt-get update
apt-get install -yq git supervisor python python-pip virtualenv

# Account to own server process
useradd -m -d /home/pythonapp pythonapp

# Fetch source code
export HOME=/root
git clone https://github.com/davidrojj/options-ws-client.git /opt/app

# Python environment setup
virtualenv -p python3 /opt/app/options-ws-client/venv
source /opt/app/options-ws-client/venv/bin/activate
/opt/app/options-ws-client/venv/bin/pip install -r /opt/app/options-ws-client/requirements.txt

# Set ownership to newly created account
chown -R pythonapp:pythonapp /opt/app

# Put supervisor configuration in proper place
cp /opt/app/options-ws-client/supervisor.conf /etc/supervisor/conf.d/supervisor.conf

# Start service via supervisorctl
supervisorctl reread
supervisorctl update
# [END getting_started_gce_startup_script]