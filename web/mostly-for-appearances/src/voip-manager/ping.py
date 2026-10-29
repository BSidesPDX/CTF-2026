import os
import time

import requests

from bootstrap_users import password

VOIP_HOST = os.environ["VOIP_HOST"]

s = requests.session()

# handle this in separate container
if os.environ.get("PING_CONTAINER") is not None:
    print("starting pinger...")
    while True:
        try:
            s.get(
                f"http://apache/login?username=theresa&password={password}",
                headers={"Host": "voipadmin.tangerineprinting.biz"},
                allow_redirects=False,
            )
        except Exception as e:
            print(f"ping error: {e}")

        time.sleep(5)
