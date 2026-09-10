"""DataUpdateCoordinator for Contact Energy."""
from datetime import date, timedelta
import logging
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

API_BASE = "https://myaccount.contact.co.nz"
API_KEY = "contact-energy-public-key"

class ContactEnergyCoordinator(DataUpdateCoordinator):
    """Coordinator fetching daily/monthly interval usage."""

    def __init__(self, hass: HomeAssistant, username: str, password: str):
        super().__init__(
            hass,
            _LOGGER,
            name="Contact Energy Usage",
            update_interval=timedelta(hours=6),
        )
        self.username = username
        self.password = password
        self.token = None
        self.account_id = None
        self.contract_id = None

    async def _authenticate(self, session: aiohttp.ClientSession) -> str:
        headers = {"Content-Type": "application/json", "x-api-key": API_KEY}
        login_url = f"{API_BASE}/login/v2"
        payload = {"email": self.username, "password": self.password}

        async with session.post(login_url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise UpdateFailed(f"Login failed (HTTP {resp.status}): {body}")
            data = await resp.json()
            self.token = data.get("token") or data.get("accessToken")
            return self.token

    async def _async_update_data(self):
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                if not self.token:
                    await self._authenticate(session)

                async def fetch_with_retry(url: str):
                    headers = {
                        "x-api-key": API_KEY,
                        "authorization": f"Bearer {self.token}",
                        "session": self.token,
                    }
                    resp = await session.get(url, headers=headers)
                    if resp.status == 401:
                        await self._authenticate(session)
                        headers["authorization"] = f"Bearer {self.token}"
                        headers["session"] = self.token
                        resp = await session.get(url, headers=headers)
                    if resp.status != 200:
                        raise UpdateFailed(f"Failed request to {url}: {resp.status}")
                    return await resp.json()

                if not self.contract_id or not self.account_id:
                    acc_data = await fetch_with_retry(f"{API_BASE}/accounts/v2")
                    summary = acc_data.get("accountsSummary", [])[0]
                    self.account_id = summary.get("id")
                    self.contract_id = summary.get("contracts", [])[0].get("contractId")

                today = date.today()
                start_date = (today - timedelta(days=365)).replace(day=1).isoformat()
                end_date = today.isoformat()

                usage_url = (
                    f"{API_BASE}/usage/v2/{self.contract_id}"
                    f"?ba={self.account_id}&interval=monthly&from={start_date}&to={end_date}"
                )
                records = await fetch_with_retry(usage_url)
                if not records:
                    return {}

                current_month = records[-1]
                total_kwh = float(current_month.get("value", 0))
                free_kwh = float(current_month.get("unchargedValue", 0))
                billed_kwh = max(0.0, total_kwh - free_kwh)
                cost_nzd = float(current_month.get("dollarValue", 0))

                return {
                    "current": {
                        "total_kwh": round(total_kwh, 2),
                        "free_kwh": round(free_kwh, 2),
                        "billed_kwh": round(billed_kwh, 2),
                        "cost_nzd": round(cost_nzd, 2),
                        "date": current_month.get("date"),
                    },
                    "history": records,
                }
            except aiohttp.ClientError as err:
                raise UpdateFailed(f"Network error: {err}") from err
