# just an example. quite complex to get the auth directly from the CAC. Preferred to use playwright so that the system OS prompts for PIN and handles auth

import requests

resp = requests.get(
    "https://ems.sec.usace.army.mil/api/rest/CHIEFS/CEMVR",
    cert=("mycert.pem", "mykey.pem"),
    verify="ca-bundle.crt"
)
print(resp.json())