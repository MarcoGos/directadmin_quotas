"""Constants for the DirectAdmin quotas integration."""

NAME = "DirectAdmin Quotas"
DOMAIN = "directadmin_quotas"
MODEL = "Quota"
MANUFACTURER = "DirectAdmin"

# Platforms
SENSOR = "sensor"
PLATFORMS = [SENSOR]

DEFAULT_SYNC_INTERVAL = 3600  # seconds

CONF_HOSTNAME = "hostname"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DOMAIN = "domain"

CONF_ACCOUNTS = "accounts"
