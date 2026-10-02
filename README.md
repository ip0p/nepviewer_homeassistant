# Nepviewer Solar for Home Assistant

This integration connects Home Assistant to your NEP solar monitoring system.

## Features
- Current solar power (W)
- Energy generated today (kWh)
- Energy generated yesterday, this month, and this year (kWh)
- Total energy generated (kWh)
- Earnings today, yesterday, this month, and overall
- CO₂ savings, driving distance, and oil and tree equivalents
- Last update time as a diagnostic sensor
- System status
- Model, serial number, firmware, and other device information
- Multiple systems per NEPViewer account
- Automatic renewal of expired API tokens

## Installation

[![Open your Home Assistant instance and add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ip0p&repository=nepviewer_homeassistant&category=integration)

1. Add the repository to HACS using the button above, or add it as a custom repository.
2. Install the **Nepviewer Solar** integration.
3. Set up the integration under **Settings → Devices & services → Add integration**.
4. Sign in with the same email address and password you use for the NEPViewer app.

## Notes
- The integration automatically signs in again when the short-lived NEPViewer token expires.
- Tested with the v2 API at nepviewer.net and Home Assistant 2026.9.4.
- Existing configurations using an old token will show a repair dialog to sign in once it expires.

## Development

Run the API tests with `pytest -q tests/test_nepviewer_api.py`. They check the
current request signature, sign-in, and automatic token renewal.

## License
MIT License
