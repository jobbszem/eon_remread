# EON Remote Read - Home Assistant Integration

Ez egy egyedi Home Assistant integráció (EON Remote Read / EON Távleolvasás), amely az EON portál REST API-ján keresztül kéri le az áramszámláló adatait és megjeleníti az elhasznált (A+) és visszatermelt (A-) energiát.

## Funkciók

- Két szenzor automatikus létrehozása:
  - **Grid Energy Import** (A+ - Elhasznált energia) - `eon_remread.grid_energy_import`
  - **Grid Energy Export** (A- - Visszatermelt energia) - `eon_remread.grid_energy_export`
- Frissítés meghatározott időpontokban (alapértelmezetten 6:00, 7:00, 9:00 és a betöltéskor aktuális óra)
- `total_increasing` state class az energia monitoring támogatásához
- REST API integráció az EON portállal
- Automatikus token kezelés és újrabejelentkezés
- **Több napos backfill**: az utolsó 7 nap adatait lekéri és időbélyeggel importálja a HA statisztikába, így a késleltetett (D+1) adatok is helyesen jelennek meg a grafikonokon és az Energy dashboardon.

## Telepítés

### 1. HACS telepítés (ajánlott)

1. Nyisd meg a HACS-t a Home Assistant-ban
2. Kattints a "Integrations" fülre
3. Kattints a három pontra (⋮) a jobb felső sarokban
4. Válaszd a "Custom repositories" opciót
5. Add hozzá ezt a repository-t:
   - Repository: `https://github.com/your_username/eon-energy`
   - Category: Integration
6. Keresd meg az "EON Remote Read" integrációt és telepítsd

### 2. Manuális telepítés

1. Másold a `custom_components/eon_remread` mappát a Home Assistant `config` könyvtárába
2. Ha még nem létezik, hozd létre a `custom_components` mappát
3. Indítsd újra a Home Assistant-ot

## Konfiguráció

1. Menj a Home Assistant **Settings** → **Devices & Services** menüpontra
2. Kattints az **"Add Integration"** gombra
3. Keress rá az **"EON Remote Read"** integrációra
4. Add meg az EON portál bejelentkezési adataidat:
   - **Username (Email)**: Az EON portál email címed
   - **Password**: Az EON portál jelszavad
   - **POD ID** (opcionális): Az áramszámláló POD azonosítója (pl. `HU000210F11-S00000000000016049191`)
     - Ha nem adod meg, az integráció megpróbálja automatikusan lekérdezni
5. Kattints a **"Submit"** gombra

A Home Assistant automatikusan létrehozza a szenzorokat és elkezdi lekérdezni az adatokat.

## API Működés

Az integráció a következő REST API végpontokat használja:

1. **Login**: `POST /sap/opu/odata/sap/ZWB5_ONLINE_SRV/Login`
   - Bejelentkezés az EON portálra
   - Visszaad egy GUID tokent, amit a következő hívásokhoz használ

2. **Get Data**: `GET /sap/opu/odata/sap/ZWB5_W1000/MeasData`
   - Lekéri az áramadatok (A+ és A-) a megadott dátumtartományra
   - Bearer token autentikációt használ
   - A hívás `MeasVarList='+A,-A,DP_1-1:1.8.0*0,DP_1-1:2.8.0*0'`: +A/-A az intervallum értékek, 1.8.0 / 2.8.0 a kumulált (napi) óraállás. A statisztika import ezeket használja, ha az API adatban szerepelnek (Num3/Num4).

Az integráció automatikusan kezeli a token lejáratát és újra bejelentkezik szükség esetén.

### Grafikonok és késleltetett adatok (backfill)

Az integráció minden frissítéskor az **utolsó 7 nap** adatait is lekéri, és a kapott pontokat **időbélyeggel** importálja a Home Assistant statisztikába (`async_import_statistics`). Így ha a szolgáltatás másnap adja meg a teljes napi adatot, a következő frissítéskor az már bekerül a megfelelő napra, és a grafikonok / Energy dashboard helyesen mutatják.

## Szenzorok

### eon_remread.grid_energy_import
- **Név**: Grid Energy Import
- **Device Class**: Energy
- **Unit**: kWh
- **State Class**: total_increasing
- **Leírás**: Az összes elhasznált energia (A+) kWh-ban (mai napra)

### eon_remread.grid_energy_export
- **Név**: Grid Energy Export
- **Device Class**: Energy
- **Unit**: kWh
- **State Class**: total_increasing
- **Leírás**: Az összes visszatermelt energia (A-) kWh-ban (mai napra)

## Frissítési intervallum

Az integráció a megadott órákban frissíti az adatokat (alapértelmezetten 6:00, 7:00, 9:00, plusz a HA indulásakor aktuális óra). Az órák a `sensor.py` fájlban az `UPDATE_HOURS` listában módosíthatók (pl. `UPDATE_HOURS = [6, 7, 9, 12, 18]`).

## Biztonság

- A jelszó a Home Assistant konfigurációs fájlban van tárolva titkosítva
- A token csak memóriában van tárolva, nem kerül mentésre
- A token automatikusan lejár és újra kell jelentkezni

## Hibaelhárítás

### "Authentication failed"

- Ellenőrizd, hogy helyes-e a felhasználónév és jelszó
- Ellenőrizd, hogy elérhető-e az EON portál
- Nézd meg a Home Assistant log fájlokat részletesebb hibákért

### Szenzorok nem jelennek meg

- Indítsd újra a Home Assistant-ot a telepítés után
- Ellenőrizd a Home Assistant log fájlokat hibákért
- Győződj meg róla, hogy helyesek-e a bejelentkezési adatok

### Értékek nem frissülnek

- Ellenőrizd az internetkapcsolatot
- Nézd meg a Home Assistant log fájlokat frissítési hibákért
- Ellenőrizd, hogy elérhető-e az EON portál API-ja

### "POD ID not found"

- Add meg manuálisan a POD ID-t a konfigurációban
- A POD ID-t az EON portálon találod meg az áramszámláló adatainál

## Fejlesztés

Ez az integráció a Home Assistant custom component struktúráját követi:
- `__init__.py` - Integráció inicializálása
- `config_flow.py` - Konfigurációs folyamat
- `sensor.py` - Szenzor entitások
- `eonnext.py` - REST API kommunikáció és adatfeldolgozás
- `manifest.json` - Integráció metaadatok
- `strings.json` és `translations/` - Lokalizáció

## Függőségek

- `aiohttp>=3.8.0` - Aszinkron HTTP kliens a REST API hívásokhoz

## Licenc

[WTFPL](https://www.wtfpl.net/)
