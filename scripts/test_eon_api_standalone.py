#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EON integráció tesztelése HA nélkül.
Az eon_remread komponens EonEnergyData osztályát használja: login, API hívás, parse, óránkénti
kumulált számítás. Kiírja a mai szenzor értékeket és azt, mit töltene be a HA statisztikába.

Használat:
  export EON_USER="email@example.com"
  export EON_PASS="jelszo"
  export EON_POD="HU000210F11-S00000000000016049191"
  python scripts/test_eon_api_standalone.py

Vagy: python scripts/test_eon_api_standalone.py <user> <password> [pod]

Futtatás az eon-remread mappa gyökeréből.
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# HA nélkül futtatható: az eon_remread csak _import_statistics-ban importál HA-t (lazy)
ROOT = Path(__file__).resolve().parent
if (ROOT / "eon-remread").is_dir():
    EON_REMREAD_ROOT = ROOT / "eon-remread"
elif (ROOT / "custom_components").is_dir():
    EON_REMREAD_ROOT = ROOT
elif (ROOT.parent / "custom_components").is_dir():
    EON_REMREAD_ROOT = ROOT.parent
else:
    EON_REMREAD_ROOT = ROOT
if str(EON_REMREAD_ROOT) not in sys.path:
    sys.path.insert(0, str(EON_REMREAD_ROOT))

try:
    from custom_components.eon_remread.eon_remread import (
        BACKFILL_DAYS,
        EonEnergyData,
    )
except ImportError as e:
    print(f"Import hiba (eon_remread): {e}")
    print("Futtasd a scriptet az eon-remread mappa gyökeréből: python scripts/test_eon_api_standalone.py")
    sys.exit(1)

try:
    import aiohttp  # noqa: F401
except ImportError:
    print("Hiányzó függőség: pip install aiohttp")
    sys.exit(1)


async def run(
    username: str,
    password: str,
    pod: str,
) -> None:
    eon = EonEnergyData(username=username, password=password, pod=pod, hass=None)
    try:
        print("Bejelentkezés...")
        if not await eon.login():
            print("Login sikertelen (nincs Guid a válaszban).")
            return
        print("Login OK.\n")

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=1, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)

        # Mai nap összesítés (ugyanaz, amit a HA szenzor mutat)
        imp_today, exp_today = await eon._get_energy_data(today_start, today_end)
        print("--- Mai szenzor értékek (amit a HA szenzorok mutatnának) ---")
        print(f"  Grid Energy Import (A+): {imp_today:.3f} kWh")
        print(f"  Grid Energy Export (A-): {exp_today:.3f} kWh")
        print()

        # Utolsó BACKFILL_DAYS nap: ugyanaz a logika, mint update() (HA nélkül)
        all_timeseries = []
        for day_offset in range(BACKFILL_DAYS):
            day_start = (today_start - timedelta(days=day_offset)).replace(
                hour=0, minute=0, second=1, microsecond=0
            )
            day_end = day_start.replace(hour=23, minute=59, second=59, microsecond=0)
            data = await eon._request_energy_data(day_start, day_end)
            if data:
                all_timeseries.extend(eon._parse_energy_data_timeseries(data))
            else:
                print(f"  Figyelem: {day_start.date()} adat nem érkezett.")

        if not all_timeseries:
            print("Nincs idősor adat a statisztikához.")
            return

        all_timeseries.sort(key=lambda x: x[0])
        import_hourly, export_hourly = eon._build_hourly_cumulative(all_timeseries)

        print("--- HA statisztika import (visszamenőleg) ---")
        print("  Az alábbi pontok kerülnének a HA-ba (sensor.grid_energy_import / sensor.grid_energy_export):")
        print()
        print("  Dátum (UTC)      Óra   Import (kWh)  Export (kWh)")
        print("  " + "-" * 52)
        for (dt_imp, val_imp), (dt_exp, val_exp) in zip(import_hourly, export_hourly):
            assert dt_imp == dt_exp
            print(f"  {dt_imp.strftime('%Y-%m-%d')}  {dt_imp.hour:02d}:00   {val_imp:>12.3f}  {val_exp:>12.3f}")
        print("  " + "-" * 52)
        print(f"  Összesen {len(import_hourly)} órás pont (import és export).")
        print()
        print("Kész. A HA-ban az Energy dashboard ezeket az időbélyegű pontokat használná a grafikonokhoz.")
    finally:
        await eon.close()


def main():
    parser = argparse.ArgumentParser(description="EON API teszt HA nélkül (eon_remread kódot használ)")
    parser.add_argument("user", nargs="?", default=os.environ.get("EON_USER"), help="EON felhasználó (email)")
    parser.add_argument("password", nargs="?", default=os.environ.get("EON_PASS"), help="EON jelszó")
    parser.add_argument("pod", nargs="?", default=os.environ.get("EON_POD", ""), help="POD ID")
    args = parser.parse_args()
    if not args.user or not args.password:
        print("Használat: EON_USER és EON_PASS környezeti változók, vagy: python scripts/test_eon_api_standalone.py <user> <password> [pod]")
        sys.exit(1)
    if not args.pod:
        print("Figyelem: EON_POD nincs megadva, a MeasData hívás hibás lehet.")
    asyncio.run(run(args.user, args.password, args.pod))


if __name__ == "__main__":
    main()
