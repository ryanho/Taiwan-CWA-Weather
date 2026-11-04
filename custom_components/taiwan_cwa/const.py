"""Constants and shared helpers for the Taiwan CWA Weather integration."""
from __future__ import annotations

import ssl
from datetime import timedelta

from homeassistant.core import HomeAssistant

DOMAIN = "taiwan_cwa"
CONF_API_KEY = "api_key"
CONF_ZONE = "zone"
# Resolved at setup from the zone's coordinates (see location.py).
CONF_LOCATION = "location"
# Options: "auto" or a manually chosen O-A0001-001 StationId.
CONF_STATION = "station"
CONF_RELOCATE = "relocate"
STATION_AUTO = "auto"

API_BASE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
OBSERVATION_DATASET = "O-A0001-001"
# Queries several township forecast datasets at once (max 5 per request).
MULTI_FORECAST_DATASET = "F-D0047-093"
MULTI_FORECAST_BATCH = 5

OBSERVATION_SCAN_INTERVAL = timedelta(minutes=10)
FORECAST_SCAN_INTERVAL = timedelta(hours=1)
# Forecasts are issued every few hours; keep showing the last one through
# transient API failures.
FORECAST_VALID = timedelta(hours=12)

TIME_ZONE = "Asia/Taipei"

# Township forecast datasets per county: (3-day hourly/3-hourly, 1-week 12-hourly).
COUNTY_FORECAST_DATASETS = {
    "宜蘭縣": ("F-D0047-001", "F-D0047-003"),
    "桃園市": ("F-D0047-005", "F-D0047-007"),
    "新竹縣": ("F-D0047-009", "F-D0047-011"),
    "苗栗縣": ("F-D0047-013", "F-D0047-015"),
    "彰化縣": ("F-D0047-017", "F-D0047-019"),
    "南投縣": ("F-D0047-021", "F-D0047-023"),
    "雲林縣": ("F-D0047-025", "F-D0047-027"),
    "嘉義縣": ("F-D0047-029", "F-D0047-031"),
    "屏東縣": ("F-D0047-033", "F-D0047-035"),
    "臺東縣": ("F-D0047-037", "F-D0047-039"),
    "花蓮縣": ("F-D0047-041", "F-D0047-043"),
    "澎湖縣": ("F-D0047-045", "F-D0047-047"),
    "基隆市": ("F-D0047-049", "F-D0047-051"),
    "新竹市": ("F-D0047-053", "F-D0047-055"),
    "嘉義市": ("F-D0047-057", "F-D0047-059"),
    "臺北市": ("F-D0047-061", "F-D0047-063"),
    "高雄市": ("F-D0047-065", "F-D0047-067"),
    "新北市": ("F-D0047-069", "F-D0047-071"),
    "臺中市": ("F-D0047-073", "F-D0047-075"),
    "臺南市": ("F-D0047-077", "F-D0047-079"),
    "連江縣": ("F-D0047-081", "F-D0047-083"),
    "金門縣": ("F-D0047-085", "F-D0047-087"),
}

# Location resolution rules (see location.py).
MAX_TOWNSHIP_DISTANCE_KM = 50
HIGHWAY_STATION_PREFIX = "CA"
HIGHWAY_FALLBACK_RADIUS_KM = 10
MAX_ALTITUDE_DIFFERENCE_M = 300
AUTO_STATION_COUNT = 3
MANUAL_STATION_CHOICES = 10

# CWA forecast WeatherCode values, from the official 預報產品天氣描述代碼表
# (https://www.cwa.gov.tw/V8/assets/pdf/Weather_Icon.pdf). Code 40 is unused.
# Labels live in the translations under entity.sensor.weather_code.state.
WEATHER_CODES = [f"{code:02d}" for code in range(1, 43) if code != 40]

# TWCA certificate chain for opendata.cwa.gov.tw.
#
# The CWA endpoint is served by a certificate that chains up to the
# "TWCA Global Root CA". We bundle that root together with its
# "TWCA Secure SSL Certification Authority" intermediate so TLS verification
# still succeeds when either:
#   * the Home Assistant host has an outdated CA store that predates the
#     TWCA Global Root CA, or
#   * the CWA server intermittently omits the intermediate certificate
#     (Python, unlike desktop browsers, does not fetch missing intermediates
#     via the AIA extension).
# This keeps full certificate verification — the chain always terminates at
# the publicly trusted TWCA Global Root CA — so the API key is never sent over
# an unverified TLS connection. The bundle is additive: if CWA rotates to a
# different chain in the future, the host's own CA store still verifies it.
TWCA_CA_BUNDLE = """\
-----BEGIN CERTIFICATE-----
MIIFQTCCAymgAwIBAgICDL4wDQYJKoZIhvcNAQELBQAwUTELMAkGA1UEBhMCVFcx
EjAQBgNVBAoTCVRBSVdBTi1DQTEQMA4GA1UECxMHUm9vdCBDQTEcMBoGA1UEAxMT
VFdDQSBHbG9iYWwgUm9vdCBDQTAeFw0xMjA2MjcwNjI4MzNaFw0zMDEyMzExNTU5
NTlaMFExCzAJBgNVBAYTAlRXMRIwEAYDVQQKEwlUQUlXQU4tQ0ExEDAOBgNVBAsT
B1Jvb3QgQ0ExHDAaBgNVBAMTE1RXQ0EgR2xvYmFsIFJvb3QgQ0EwggIiMA0GCSqG
SIb3DQEBAQUAA4ICDwAwggIKAoICAQCwBdvI64zEbooh745NnHEKH1Jw7W2CnJfF
10xORUnLQEK1EjRsGcJ0pDFfhQKX7EMzClPSnIyOt7h52yvVavKOZsTuKwEHktSz
0ALfUPZVr2YOy+BHYC8rMjk1Ujoog/h7FsYYuGLWRyWRzvAZEk2tY/XTP3VfKfCh
MBwqoJimFb3u/Rk28OKRQ4/6ytYQJ0lM793B8YVwm8rqqFpD/G2Gb3PpN0Wp8DbH
zIh1HrtsBv+baz4X7GGqcXzGHaL3SekVtTzWoWH1EfcFbx39Eb7QMAfCKbAJTibc
46KokWofwpFFiFzlmLhxpRUZyXx1EcxwdE8tmx2RRP1WKKD+u4ZqyPpcC1jcxkt2
yKsi2XMPpfRaAok/T54igu6idFMqPVMnaR1sjjIsZAAmY2E2TqNGtz99sy2sbZCi
laLOz9qC5wc0GZbpuCGqKX6mOL6OKUohZnkfs8O1CWfe1tQHRvMq2uYiN2DLgbYP
oA/pyJV/v1WRBXrPPRXAb94JlAGD1zQbzECl8LibZ9WYkTunhHiVJqRaCPgrdLQA
BDzfuBSO6N+pjWxnkjMdwLfS7JLIvgm/LCkFbwJrnu+8vyq8W8BQj0FwcYeyTbcE
qYSjMq+u7msXi7Kx/mzhkIyIqJdIzshNy/MGz19qCkKxHh53L46g5pIOBvwFItIm
4TFRfTLcDwIDAQABoyMwITAOBgNVHQ8BAf8EBAMCAQYwDwYDVR0TAQH/BAUwAwEB
/zANBgkqhkiG9w0BAQsFAAOCAgEAXzSBdu+WHdXltdkCY4QWwa6gcFGn90xHNcgL
1yg9iXHZqjNB6hQbbCEAwGxCGX6faVsgQt+i0trEfJdLjbDorMjupWkEmQqSpqsn
LhpNgb+E1HAerUf+/UqdM+DyucRFCCEK2mlpc3INvjT+lIutwx4116KD7+U4x6WF
H6vPNOw/KP4M8VeGTslV9xzU2KV9Bnpv1d8Q34FOIWWxtuEXeZVFBs5fzNxGiWNo
RI2T9GRwoD2dKAXDOXC4Ynsg/eTb6QihuJ49CcdP+yz4k3ZB3lLg4VfSnQO8d57+
nile98FRYB/e2guyLXW3Q0iT5/Z5xoRdgFlglPx4mI88k1HtQJAH32RjJMtOcQWh
15QaiDLxInQirqWm2BJpTGCjAu4r7NRjkgtevi92a6O2JryPA9gK8kxkRr05YuWW
6zRjESjMlfGt7+/cgFhI6Uu46mWs6fyAtbXIRfmswZ/ZuepiiI7E8UuDEq3mi4TW
nsLrgxifarsbJGAzcMzs9zLzXNl5fe+epP7JI8Mk7hWSsT2RTyaGvWZzJBPqpK5j
wa19hAM8EHiGG3njxPPyBJUgriOCxLM6AGK/5jYk4Ve6xx6QddVfP5VhK8E7zeWz
aGHQRiapIVJpLesux+t3zqY6tQMzT3bR51xUAV3LePTJDL/PEo4XLSNolOer/qmy
KwbQBM0=
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
MIIFxjCCA66gAwIBAgIQQAE0s2gAAAAAAAAM0KoI7DANBgkqhkiG9w0BAQsFADBR
MQswCQYDVQQGEwJUVzESMBAGA1UEChMJVEFJV0FOLUNBMRAwDgYDVQQLEwdSb290
IENBMRwwGgYDVQQDExNUV0NBIEdsb2JhbCBSb290IENBMB4XDTIzMTAxNjA5MDEw
NFoXDTMwMTAxNjE1NTk1OVowUzELMAkGA1UEBhMCVFcxEjAQBgNVBAoTCVRBSVdB
Ti1DQTEwMC4GA1UEAxMnVFdDQSBTZWN1cmUgU1NMIENlcnRpZmljYXRpb24gQXV0
aG9yaXR5MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAyS5amjYQhd10
hZs00r7RXdI3ASka2AQmJnOyA6bqvAYOMlMECUdlsjDccdmMdHx8YTYYMtmCy+UB
RJZ/ytVANVQlfcUvXzWfauFs8XpCC/Th+Ed2tIEEGK218QsBebImAHPGDvp2Yglj
XVaQR/0FeN1lIzQ3iUkad0dCsC/bxFiWsmsjeSscTaxrYzHFADUhK0qj4W5PmOuw
lAR3C4XXgzPAI3V0qBpQ7sqgNLaNBFTZkP6AVryZC+DapfWBIMmIxIOg8g25MKb4
XvXkCLYKIxi8Djhv1zSmLLrKbQFZrjWlD/OWqInPPmSwBrKZ13EMQhoRRi1pXfN+
J2ugR/PUQQIDAQABo4IBljCCAZIwHwYDVR0jBBgwFoAUSNvN3o7pSXJaiOix2D0H
s7lrZlAwHQYDVR0OBBYEFJLn+mIWcYzzl3FCxgan4EZhS1y2MA4GA1UdDwEB/wQE
AwIBhjAdBgNVHSUEFjAUBggrBgEFBQcDAQYIKwYBBQUHAwIwSgYDVR0gBEMwQTA1
BgsrBgEEAYK/JQEBFTAmMCQGCCsGAQUFBwIBFhhodHRwczovL3d3dy50d2NhLmNv
bS50dy8wCAYGZ4EMAQICMEkGA1UdHwRCMEAwPqA8oDqGOGh0dHA6Ly9yb290Y2Eu
dHdjYS5jb20udHcvVFdDQVJDQS9nbG9iYWxfcmV2b2tlXzQwOTYuY3JsMBIGA1Ud
EwEB/wQIMAYBAf8CAQAwdgYIKwYBBQUHAQEEajBoMDwGCCsGAQUFBzAChjBodHRw
Oi8vc3Nsc2VydmVyLnR3Y2EuY29tLnR3L2NhY2VydC9yb290NDA5Ni5jcnQwKAYI
KwYBBQUHMAGGHGh0dHA6Ly9yb290b2NzcC50d2NhLmNvbS50dy8wDQYJKoZIhvcN
AQELBQADggIBADVzQW2rRsMiWoVrBdZX1BiOgN6B/Ryt2zpq8uRxFQspvGYfUVIm
4uU4AaPR7aQ5KwpKjDWv2ncvX2ssCY54B82g2mxEEVEdu5PFl0jkuk4LmPsClYZc
6J6odUbVI3wtv2yF6+fqQrO+gDhEIhlg3IqWICfiyJZS+p2TirMszGzs4a+K9tZX
rS2W/jKsSt4bSmcIzDpwm2gSaSuLDIAwq0WrD29kA7+N+rMMs4zBIVKyYm9r08q4
UOGU16J7mKBrF0KYDZFyT9Hq5HAX2uwYoQJxQ5Z0BR8eZH8AIIi2vsFC8pkv2ra1
2dldd3Pivm0mdratbn1Z6MQ71FKR9Ui3L8P+0xu8DkhhxE11Ogpl+aquBUqGcvlD
0SgpXy+eoeFaRhFXRUkWtH/3XYo+h+N+4jZmgjCLd4+YI+u5tbUGpyBMABmUDiqZ
xcrPGc4cvXExqYePUg6cFCDcjqGCxqSu5BPbA5R+DSTkn5Sc1WQzORJpD5b7pcEq
8msolev88dcmddLXMyWzXQfPHA4vaQD74lr5LIzn6BRjVv+ZB7Y0ZTnnOimDXxn7
Cxqd+1/8ldRis/tO/JWZsMm5ruvCppwCZUdXjSNI5R1OxzVwTVLzsCoiSYPV0agd
a5dQ9wayB6OohBK7+ZU2V3sZwE2xwHdDzfhbdzmI++TxtOurDHbkfkED
-----END CERTIFICATE-----
"""

_cwa_ssl_context: ssl.SSLContext | None = None


def _build_cwa_ssl_context() -> ssl.SSLContext:
    """Create a verifying SSL context that tolerates CWA's certificate quirks.

    Two problems have to be solved without disabling verification (which would
    leak the API key to on-path attackers):

    1. Missing Subject Key Identifier. The certificate chain served by
       opendata.cwa.gov.tw trips the strict RFC 5280 extension checks. Python
       3.13's ssl.create_default_context() enables VERIFY_X509_STRICT by
       default, so OpenSSL rejects the chain with
       "certificate verify failed: Missing Subject Key Identifier". Clearing
       that one flag relaxes the pedantic extension checks while still
       verifying the signature chain, host name, expiry and trust anchor — the
       SKI is only a chain-building hint, not a security control, so MITM
       protection stays intact.

    2. CA availability. The TWCA root + intermediate are bundled in so the
       chain still completes if the host CA store predates the TWCA Global Root
       CA or the server omits its intermediate. This is additive: a future
       chain rotation is still verified by the host CA store.
    """
    context = ssl.create_default_context()
    context.load_verify_locations(cadata=TWCA_CA_BUNDLE)
    context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context


async def async_get_cwa_ssl_context(hass: HomeAssistant) -> ssl.SSLContext:
    """Return a cached verifying SSL context that trusts the TWCA chain.

    Built once in the executor because create_default_context() reads the
    system CA bundle from disk, which must not block the event loop.
    """
    global _cwa_ssl_context
    if _cwa_ssl_context is None:
        _cwa_ssl_context = await hass.async_add_executor_job(_build_cwa_ssl_context)
    return _cwa_ssl_context
