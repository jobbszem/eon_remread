# Scripts – EON API tesztelés HA nélkül

## test_eon_api_standalone.py

Ez a script az **eon_remread** komponens kódját használja (login, API hívás, parse, óránkénti kumulált számítás), de **Home Assistant nélkül** futtatható. Célja:

- Bejelentkezés az EON e-portál API-jára
- Mai nap A+ / A− összesítésének lekérése (amit a HA szenzorok mutatnának)
- Utolsó 7 nap adatának lekérése és óránkénti kumulált listák készítése (amit a HA statisztika import kapna)

A kimeneten látod a mai szenzor értékeket és az óránkénti pontokat, amiket az Energy dashboard használna.

### Követelmények

- Python 3.9+
- **aiohttp**: `pip install aiohttp`

### Futtatás

Mindig az **eon-remread** mappa gyökeréből futtasd (ahol a `custom_components` mappa is van):

```bash
cd eon-remread
python scripts/test_eon_api_standalone.py
```

### Bejelentkezési adatok

Adja meg az EON portál adatait **környezeti változókkal** vagy **parancssori argumentumokkal**.

**Környezeti változók (Linux/macOS):**

```bash
export EON_USER="email@example.com"
export EON_PASS="jelszavad"
export EON_POD="HU000210F11-S00000000000016049191"
python scripts/test_eon_api_standalone.py
```

**Windows (PowerShell):**

```powershell
$env:EON_USER = "email@example.com"
$env:EON_PASS = "jelszavad"
$env:EON_POD = "HU000210F11-S00000000000016049191"
python scripts/test_eon_api_standalone.py
```

**Parancssori argumentumok:**

```bash
python scripts/test_eon_api_standalone.py "email@example.com" "jelszavad" "HU000210F11-S00000000000016049191"
```

A POD ID opcionális, de a MeasData hívás hibás lehet nélküle. A POD azonosítót az EON portálon az áramszámláló adatainál találod.

### Példa kimenet

```
Bejelentkezés...
Login OK.

--- Mai szenzor értékek (amit a HA szenzorok mutatnának) ---
  Grid Energy Import (A+): 12.345 kWh
  Grid Energy Export (A-): 2.100 kWh

--- HA statisztika import (visszamenőleg) ---
  Az alábbi pontok kerülnének a HA-ba ...
  Dátum (UTC)      Óra   Import (kWh)  Export (kWh)
  ----------------------------------------------------
  2025-01-27  00:00         1234.567       567.890
  ...
  Összesen 168 órás pont (import és export).

Kész. A HA-ban az Energy dashboard ezeket az időbélyegű pontokat használná a grafikonokhoz.
```

### Futtatás a szülő repo gyökeréből (Eon)

Ha a projekt a nagyobb **Eon** repo része, és az **eon-remread** mappa a repo gyökerében van:

```bash
cd Eon
python eon-remread/scripts/test_eon_api_standalone.py
```

A script felismeri az elérési utat és ugyanúgy betölti az eon_remread komponenst.
