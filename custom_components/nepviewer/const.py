"""Constants for the NEPViewer integration."""

DOMAIN = "nepviewer"

CONF_ACCOUNT = "account"
CONF_COMPANY_ID = "company_id"

API_BASE_URL = "https://api.nepviewer.net/"
LOGIN_ENDPOINT = "v2/sign-in"
SITES_ENDPOINT = "v2/site/listWithSN"
DEVICE_DETAIL_ENDPOINT = "v2/device/detail"
DEVICE_OVERVIEW_ENDPOINT = "v2/device/statistics/overview"

DEFAULT_COMPANY_ID = 0
DEFAULT_LANGUAGE = 6
UPDATE_INTERVAL_SECONDS = 60
