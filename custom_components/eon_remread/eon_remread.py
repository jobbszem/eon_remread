#!/usr/bin/env python3

"""
EON Remote Read / EON Távleolvasás
"""

import base64
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import aiohttp

from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData


# (dt, num1, num2, num3_opt, num4_opt) - Num3=1.8.0 kumulált import, Num4=2.8.0 kumulált export
TimeseriesPoint = Tuple[datetime, float,
                        float, Optional[float], Optional[float]]


_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://e-portal.eon-hungaria.com"
LOGIN_URL = f"{BASE_URL}/sap/opu/odata/sap/ZWB5_ONLINE_SRV/Login?sap-language=HU"
DATA_URL = f"{BASE_URL}/sap/opu/odata/sap/ZWB5_W1000/MeasData"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/144.0.0.0 Safari/537.36")

# Több nap lekérése a késleltetett adatok pótlásához (grafikonok)
BACKFILL_DAYS = 7
# +A,-A = intervallum fogyasztás/visszatáplálás; DP_1-1:1.8.0*0 / 2.8.0*0 = kumulált (napi) érték
MEAS_VAR_LIST = "+A,-A,DP_1-1:1.8.0*0,DP_1-1:2.8.0*0"
# Egyezzen a HA entity_id-vel (domain.object_id)
STATISTIC_ID_IMPORT = "eon_remread.grid_energy_import"
STATISTIC_ID_EXPORT = "eon_remread.grid_energy_export"


class EonEnergyData:
    """EON Energy Data handler using REST API (EON Remote Read)."""

    def __init__(
        self,
        username: str,
        password: str,
        pod: str = "",
        hass: Optional[object] = None,
    ):
        """Initialize the EON Energy Data handler."""
        self.username = username
        self.password = password
        self.pod = pod
        self._hass = hass
        self.token: Optional[str] = None
        self.total_import = 0.0  # A+ (elhasznált)
        self.total_export = 0.0  # A- (visszatermelt)
        self.last_updated: Optional[datetime] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def login(self) -> bool:
        """Login to EON API and get token."""
        try:
            session = await self._get_session()

            headers = {
                "accept": "application/json",
                "accept-language": "en,hu;q=0.9,en-US;q=0.8",
                "content-type": "application/json",
                "origin": BASE_URL,
                "referer": f"{BASE_URL}/ugyintezes/login",
                "user-agent": USER_AGENT,
                "x-requested-with": "X",
            }

            # Jelszó Base64 kódolással küldjük
            password_b64 = base64.b64encode(
                self.password.encode("utf-8")
            ).decode("ascii")

            payload = {
                "Username": self.username,
                "Password": password_b64,
                "Guid": "",
                "Channel": "WEB",
                "PasswordInit": False,
                "FbId": "",
                "Selectedelmu": False,
                "Delegate": False,
                "Fb": False,
                "KauGuid": "",
                "ServerEvent": "L000",
                "Partners": {"results": []},
                "Message": {"results": []},
            }

            async with session.post(
                LOGIN_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 201:
                    data = await response.json()
                    guid = data.get("d", {}).get("Guid")
                    if guid:
                        self.token = guid
                        _LOGGER.info("Successfully logged in to EON API")
                        return True
                    else:
                        _LOGGER.error("Login response does not contain Guid")
                        return False
                else:
                    _LOGGER.error("Login failed with status %s",
                                  response.status)
                    return False

        except (aiohttp.ClientError, TimeoutError, ValueError) as e:
            _LOGGER.error("Error during login: %s", e)
            return False

    def _parse_timestamp(self, date_str: str) -> Optional[datetime]:
        """Parse /Date(timestamp)/ format to timezone-aware datetime."""
        match = re.match(r"/Date\((\d+)\)/", date_str)
        if match:
            return datetime.fromtimestamp(
                int(match.group(1)) / 1000, tz=timezone.utc
            )
        return None

    async def _request_energy_data(
        self, start_date: datetime, end_date: datetime
    ) -> Optional[dict]:
        """Request raw energy data from EON API. Returns JSON dict or None."""
        if not self.token:
            return None
        try:
            session = await self._get_session()
            start_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
            end_str = end_date.strftime("%Y-%m-%dT%H:%M:%S")
            url = (
                f"{DATA_URL}(Pod='{self.pod}',"
                f"MeasVarList='{MEAS_VAR_LIST}',"
                f"Interval='1',"
                f"StartDate=datetime'{start_str}',"
                f"EndDate=datetime'{end_str}')"
                f"?$expand=MeasDatas&sap-language=HU"
            )
            headers = {
                "accept": "application/json",
                "accept-language": "en,hu;q=0.9,en-US;q=0.8",
                "authorization": f"Bearer {self.token}",
                "authorizationerp": f"Bearer {self.token}",
                "mode": "no-cors",
                "referer": f"{BASE_URL}/w1000/tavleolv",
                "user-agent": USER_AGENT,
                "x-requested-with": "X",
            }
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    return await response.json()
                if response.status == 401 and await self.login():
                    async with session.get(
                        url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as retry_response:
                        if retry_response.status == 200:
                            return await retry_response.json()
                return None
        except (aiohttp.ClientError, TimeoutError, ValueError) as e:
            _LOGGER.error("Error requesting energy data: %s", e)
            return None

    async def _get_energy_data(
        self, start_date: datetime, end_date: datetime
    ) -> tuple[float, float]:
        """Get total import/export for a date range. Returns (import_kwh, export_kwh)."""
        data = await self._request_energy_data(start_date, end_date)
        if data is None:
            return 0.0, 0.0
        return self._parse_energy_data(data)

    def _parse_energy_data(self, data: dict) -> tuple[float, float]:
        """Parse API response to (total_import, total_export) in kWh."""
        total_a_plus = 0.0
        total_a_minus = 0.0
        results = data.get("d", {}).get("MeasDatas", {}).get("results", [])
        for entry in results:
            total_a_plus += float(entry.get("Num1", 0) or 0)
            total_a_minus += float(entry.get("Num2", 0) or 0)
        return total_a_plus, total_a_minus

    def _parse_energy_data_timeseries(self, data: dict) -> list[TimeseriesPoint]:
        """
        Parse API response to (dt, num1, num2, num3_opt, num4_opt) per interval.
        Num3 = 1.8.0 kumulált import, Num4 = 2.8.0 kumulált export (nem minden sorban van).
        """
        results = data.get("d", {}).get("MeasDatas", {}).get("results", [])
        out: list[TimeseriesPoint] = []
        for entry in results:
            ts_str = entry.get("Timestamp") or entry.get("Datum")
            dt = self._parse_timestamp(ts_str) if ts_str else None
            if dt is None:
                continue
            num1 = float(entry.get("Num1", 0) or 0)
            num2 = float(entry.get("Num2", 0) or 0)
            raw3 = entry.get("Num3")
            raw4 = entry.get("Num4")
            num3 = float(raw3) if raw3 not in (None, "") else None
            num4 = float(raw4) if raw4 not in (None, "") else None
            if num3 is not None and num3 <= 0:
                num3 = None
            if num4 is not None and num4 <= 0:
                num4 = None
            out.append((dt, num1, num2, num3, num4))
        return out

    def _build_hourly_cumulative(
        self,
        timeseries: list[TimeseriesPoint],
    ) -> tuple[
        list[tuple[datetime, float]],
        list[tuple[datetime, float]],
    ]:
        """
        Óránkénti kumulált értékek: ha van Num3/Num4 (API kumulált) az adott pontban,
        azt használjuk, különben Num1/Num2 összegéből számoljuk.
        """
        # Óránként: (sum_num1, sum_num2, utolsó num3, utolsó num4) – az óra utolsó pontjában
        hourly: dict[
            tuple[int, int, int, int],
            tuple[float, float, Optional[float], Optional[float]],
        ] = defaultdict(lambda: (0.0, 0.0, None, None))
        for dt, num1, num2, num3_opt, num4_opt in timeseries:
            key = (dt.year, dt.month, dt.day, dt.hour)
            s1, s2, _, _ = hourly[key]
            hourly[key] = (
                s1 + num1,
                s2 + num2,
                num3_opt if num3_opt is not None else hourly[key][2],
                num4_opt if num4_opt is not None else hourly[key][3],
            )
        keys_sorted = sorted(hourly.keys())
        import_list: list[tuple[datetime, float]] = []
        export_list: list[tuple[datetime, float]] = []
        cum_import = 0.0
        cum_export = 0.0
        has_cumulative = False

        for y, m, d, h in keys_sorted:
            s1, s2, last_num3, last_num4 = hourly[(y, m, d, h)]
            if last_num3 is not None:
                cum_import = last_num3
            else:
                cum_import += s1
            if last_num4 is not None:
                cum_export = last_num4
            else:
                cum_export += s2
            hour_start = datetime(
                y, m, d, h, 0, 0, 0, tzinfo=timezone.utc
            )

            # Only append if we already have a cumulative value (DP_1*)
            # AND there's interval consumption/export (A+/A-)
            if last_num3 is not None or last_num4 is not None:
                has_cumulative = True
            # has_cumulative = last_num3 is not None or last_num4 is not None
            has_interval = s1 > 0 or s2 > 0

            if has_cumulative and has_interval:
                import_list.append((hour_start, round(cum_import, 3)))
                export_list.append((hour_start, round(cum_export, 3)))

        return import_list, export_list

    async def _import_statistics(
        self,
        statistic_id: str,
        name: str,
        hourly_data: list[tuple[datetime, float]],
    ) -> None:
        """Import hourly cumulative statistics into HA for Energy dashboard."""
        if not self._hass or not hourly_data:
            _LOGGER.warning(
                "Cannot import statistics for %s: hass=%s, hourly_data_count=%d",
                statistic_id,
                self._hass is not None,
                len(hourly_data) if hourly_data else 0,
            )
            return

        statistics = [
            StatisticData(
                start=dt,
                state=value,
                sum=value,
            )
            for dt, value in hourly_data
        ]
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            mean_type=None,
            name=name,
            source="recorder",
            statistic_id=statistic_id,
            unit_of_measurement="kWh",
        )
        try:
            async_import_statistics(self._hass, metadata, statistics)
            _LOGGER.debug(
                "Imported %d points for %s (date range: %s to %s)",
                len(statistics),
                statistic_id,
                hourly_data[0][0] if hourly_data else "N/A",
                hourly_data[-1][0] if hourly_data else "N/A",
            )
        except (ValueError, TypeError) as ex:
            _LOGGER.exception(
                "Exception at async_import_statistics %s: %s",
                statistic_id,
                ex,
            )

    async def update(self) -> None:
        """Update energy data from EON API and optionally backfill statistics."""
        if not self.token:
            _LOGGER.warning("No token available, attempting to login")
            if not await self.login():
                _LOGGER.error("Failed to login")
                return

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=1, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)

        # Mai összesítés a szenzorhoz
        import_val, export_val = await self._get_energy_data(
            today_start, today_end
        )
        self.total_import = import_val
        self.total_export = export_val
        self.last_updated = datetime.now()

        # Több nap lekérése és statisztika import (grafikonok pótlása)
        if self._hass:
            all_timeseries: list[TimeseriesPoint] = []
            for day_offset in range(BACKFILL_DAYS):
                day_start = (today_start - timedelta(days=day_offset)).replace(
                    hour=0, minute=0, second=1, microsecond=0
                )
                day_end = day_start.replace(
                    hour=23, minute=59, second=59, microsecond=0
                )
                data = await self._request_energy_data(day_start, day_end)
                if data:
                    ts_count = len(self._parse_energy_data_timeseries(data))
                    all_timeseries.extend(
                        self._parse_energy_data_timeseries(data)
                    )
                    _LOGGER.debug(
                        "Retrieved %d timeseries points for %s",
                        ts_count,
                        day_start.date(),
                    )
            _LOGGER.debug("Total timeseries points from API: %d", len(all_timeseries))
            if all_timeseries:
                all_timeseries.sort(key=lambda x: x[0])
                import_hourly, export_hourly = self._build_hourly_cumulative(
                    all_timeseries
                )
                _LOGGER.debug(
                    "After _build_hourly_cumulative: import=%d points, export=%d points",
                    len(import_hourly),
                    len(export_hourly),
                )
                await self._import_statistics(
                    STATISTIC_ID_IMPORT,
                    "EON Grid Energy Import",
                    import_hourly,
                )
                await self._import_statistics(
                    STATISTIC_ID_EXPORT,
                    "EON Grid Energy Export",
                    export_hourly,
                )

        _LOGGER.info(
            "Updated energy data: Import=%.3f kWh, Export=%.3f kWh",
            import_val,
            export_val,
        )

    def get_total_import(self) -> float:
        """Get total imported energy (A+) in kWh."""
        return self.total_import

    def get_total_export(self) -> float:
        """Get total exported energy (A-) in kWh."""
        return self.total_export

    def get_last_updated(self) -> Optional[datetime]:
        """Get last update timestamp."""
        return self.last_updated
