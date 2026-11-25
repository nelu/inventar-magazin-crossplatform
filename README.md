# Magazin componente PC | 208ID

Descarcă **`Magazin.release.exe`** din secțiunea **Releases** a depozitului GitHub și pornește-l prin dublu clic pe Windows x64. Nu sunt necesare Python, Qt sau Docker pentru utilizare. La pornire nu se încarcă și nu se suprascrie niciun inventar.

## Utilizare

1. Din **Acasă**, alege **Inventar nou** și destinația CSV sau **Deschide CSV** pentru un fișier existent. Pentru demonstrație poți deschide o copie a fișierului `componente.csv` din proiectul C++.
2. În **Inventar**, consultă tabelul, adaugă un produs prin **Adăugare produs** sau selectează un rând pentru ștergere. Ștergerea solicită confirmare.
3. În **Operații de stoc**, vinde o singură bucată sau adaugă o cantitate pozitivă. Nu poți vinde dintr-un stoc epuizat.
4. În **Valoare pe categorie** poți verifica suma `preț × stoc`, iar în **Căutare după marcă** poți vedea produsele corespunzătoare. Comparațiile disting majusculele de minuscule.
5. Folosește lista din stânga sau meniul **Navigare** pentru a schimba ecranul. **F1** deschide **Ajutor**.

Modificările se salvează automat în fișierul activ. **Fișier → Salvează ca** creează o copie și continuă lucrul în acea copie. Dacă editezi CSV-ul în alt program, redeschide-l înainte de următoarea operație în Magazin. Fiecare salvare scrie mai întâi un fișier temporar în același director; dacă înlocuirea eșuează, modificarea nu este aplicată în memorie.

Formatul este UTF-8, cu nouă coloane și fără delimitare prin ghilimele:

```text
cod;pret;marca;an;garantie;producator;tara;categorie;stoc
SSD01;249.90;Exemplu;2025;24;Fabrica;RO;SSD;4
```

Codul trebuie să fie unic; anul acceptat este 1980–2026, ca în aplicația originală. Prețul din CSV folosește punct zecimal. Nu introduce `;` sau linii noi în câmpuri. Importul indică numărul liniilor ignorate (de exemplu, coduri duplicate). **La următoarea modificare, CSV-ul activ va conține doar înregistrările acceptate**; alege „Salvează ca” dacă dorești să păstrezi originalul.

## Dezvoltare și teste

Aplicația este scrisă în Python. `src/main.py` pornește Qt; `src/magazin/inventory.py` conține clasele `Product` și `Inventory`, regulile de stoc și persistența CSV. În pachetul `src/magazin/ui/`, `main_window.py` coordonează navigarea, iar modulele pentru inventar, adăugare, stoc și rapoarte gestionează propriile controale. Dialogurile și componentele comune sunt separate. `shiboken6` este necesar pentru legătura dintre PySide6 și Qt, nu pentru codul magazinului: aplicația nu apelează `main.cpp` sau `magazin.exe` din proiectul C++.

Pentru dezvoltare și compilare se folosește un singur `requirements.txt`, care include și Nuitka. Versiunile sunt fixate cu `==`, fără verificare prin hash. Pip își instalează separat instrumentele necesare pentru a construi pachetul Nuitka, într-un mediu izolat. Pentru rularea executabilului nu trebuie instalată nicio dependență. Pip, Nuitka și Python folosesc implicit depozitele de certificate ale sistemului, fără suprascrieri.

Din directorul `pyported`, pe Windows x64 cu Python 3.13:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\main.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Recompilare Windows

Pornește Docker în modul **Windows containers**. Din rădăcina proiectului:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File build-windows.ps1
```

Comanda produce **`dist/Magazin.release.exe`** pentru testare locală. Versiunile GitHub sunt compilate separat de fluxul de publicare descris mai jos.

1. **Imaginea de compilare:** `docker build` instalează instrumentele și pregătește cache-ul, fără sursele aplicației. Scriptul selectează baza după versiunea gazdei Docker: **LTSC 2019** pentru Windows 10 build 19045 sau **LTSC 2022** pentru Server 2022. Pentru o gazdă necunoscută, folosește `-BaseImage` cu o imagine MSVC compatibilă care include Chocolatey. Chocolatey instalează CPython 3.13.17 x64, iar pip instalează dependențele din `requirements.txt`. Opțiunea `-ToolingOnly` se oprește după pregătirea imaginii.
2. **Compilarea:** containerul rulează mai întâi `python -m unittest discover -s tests -v`. Dacă toate testele trec, imaginea compilează `C:/app/src/main.py` cu `--onefile` în `C:/out/Magazin.exe`, iar scriptul copiază rezultatul pe gazdă cu `docker cp`. Sursele sunt montate doar pentru citire. Izolarea implicită este Hyper-V; memoria și paralelismul rămân la valorile implicite ale Docker și Nuitka. Poți rula imaginea și direct:

   ```powershell
   docker create --name magazin-build --isolation hyperv `
     -v "${PWD}:C:\app:ro" `
     -v magazin-nuitka-cache:C:\nuitka-cache `
     magazin-tooling:windows
   docker start magazin-build
   # După ce docker inspect arată starea exited și codul 0:
   docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' magazin-build
   docker logs --tail 100 magazin-build
   docker cp magazin-build:C:/out/Magazin.exe .\dist\Magazin.release.exe
   docker rm -f magazin-build
   ```
3. **Cache și rezultat:** imaginea de compilare folosește automat `nuitka-build.py` pentru a compila o probă standalone PySide6/Shiboken. Imaginea finală păstrează Dependency Walker și rezultatele scanării DLL-urilor, fără `clcache`-ul probei. Containerul copiază intrările lipsă în volumul Docker `magazin-nuitka-cache`. Scriptul înlocuiește executabilul din `dist/` numai după ce compilarea și copierea reușesc, apoi afișează suma SHA-256. `-ReleasePath` permite alegerea altei destinații; `-CandidatePath` rămâne un alias compatibil.

### Benchmark pentru cache-ul Nuitka

Rezultate istorice pe Windows 10 build 19045, LTSC 2019, Hyper-V (secunde), dinainte de eliminarea opțiunii `none`. Măsurătorile au refolosit straturile de instalare a dependențelor, dar au executat din nou proba standalone. Pentru fiecare mod, prima compilare a folosit un volum nou, iar a doua a refolosit același volum.

| Mod | Imagine | Prima compilare | Scanare DLL, prima | `clcache` (hit/miss), prima | Repetare | Imagine + prima | Cache în imagine |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `none` | 22,6 | 452,5 | 130,36 | 0/25 | 148,8 | 475,0 | — |
| `standalone` | 376,1 | 186,1 | 0,71 | 0/25 | 153,5 | 562,2 | 1,89 MB |

`standalone` reduce prima compilare cu aproximativ 60% când imaginea este deja pregătită. Pentru o singură compilare care include și pregătirea imaginii, `none` a fost cel mai rapid; după prima compilare, volumul persistent reduce aproape complet diferența dintre moduri.

Într-un test A/B cu câte două compilări pe volume noi, păstrarea `clcache`-ului probei nu a produs niciun hit (0/25 în toate rulările). Media a fost 184,75 s fără el și 183,07 s cu el, iar imaginea a crescut cu 2,96 MB. De aceea imaginea păstrează doar cache-ul pentru descărcări și scanări DLL.

## Recompilare Linux x86-64

Pornește Docker Desktop în modul **Linux containers** sau folosește Docker Engine pe Linux. Din directorul `pyported`, în Bash (sau Git Bash pe Windows):

```bash
bash build-linux.sh
```

`Dockerfile.linux` folosește imaginea `manylinux_2_28_x86_64` (AlmaLinux 8), CPython 3.13 și GCC pentru a construi `magazin-tooling:linux`. Containerul montează proiectul doar pentru citire și rulează aceleași teste ca build-ul Windows înainte de compilare. Cache-ul persistă în volumul `magazin-nuitka-cache-linux-x64`; `NUITKA_CACHE_VOLUME` permite alegerea altui volum.

Scriptul verifică formatul ELF x86-64, afișează suma SHA-256 și exportă executabilul în `dist/Magazin-linux-x64.release`. Pe desktopul Linux îl poți porni astfel:

```bash
chmod +x dist/Magazin-linux-x64.release
./dist/Magazin-linux-x64.release
```

Pentru depanarea bibliotecilor Qt, poți porni imaginea de compilare cu `--build-standalone` în loc de comanda implicită `--build-app`. Executabilul include Python și Qt. Pentru lansarea prin X11 are nevoie de glibc 2.28 sau mai nou, GLib, Fontconfig, OpenGL și bibliotecile X11/XCB. Pe un sistem minimal, verifică inclusiv `libxcb-cursor0` (Debian/Ubuntu) sau `xcb-util-cursor` (Fedora/AlmaLinux; în EPEL 8), extensiile XCB și `libxkbcommon-x11`. GTK și CUPS sunt integrări opționale.

Executabilul onefile a trecut testul de lansare prin X11/Xvfb, deschidere, „Salvează ca” și redeschidere a unui CSV în containere curate AlmaLinux 8.10, Ubuntu 22.04 și 24.04, Debian 12 și Fedora 44. Versiunea maximă glibc cerută de executabil și de fișierele ELF din pachet este 2.28. Sesiunile desktop native Wayland nu au fost testate.

## Publicare pe GitHub

Fluxul `.github/workflows/build-release.yml` pornește numai la trimiterea unei etichete de versiune noi: `v1.2.3` pentru o versiune stabilă sau `v1.2.3-rc.1` pentru o versiune preliminară. Creează eticheta pe un commit care conține deja fluxul:

```bash
git tag -a v1.2.3 -m 'Magazin v1.2.3'
git push origin v1.2.3
```

GitHub Actions folosește aceleași scripturi Docker ca la compilarea locală și testează și compilează în paralel executabilele Windows și Linux x64. Pe runnerul `windows-2022`, scriptul folosește imaginea de bază LTSC 2022 și izolarea la nivel de proces (`-Isolation process`). După ce ambele compilări trec, fluxul publică `Magazin.release.exe`, `Magazin-linux-x64.release.tar.gz` și `SHA256SUMS` în secțiunea **Releases**. Dacă o compilare eșuează, versiunea nu se publică.

Pe Linux, descarcă arhiva și `SHA256SUMS` în același director, apoi verifică și pornește executabilul:

```bash
sha256sum --check --ignore-missing SHA256SUMS
tar -xzf Magazin-linux-x64.release.tar.gz
./Magazin-linux-x64.release
```

Pe Windows, compară rezultatul comenzii `Get-FileHash .\Magazin.release.exe -Algorithm SHA256` cu linia pentru acel fișier din `SHA256SUMS`.

## Verificarea livrării

Au trecut 8 teste pentru inventar/CSV și 5 pentru interfața Qt. Executabilul livrat a fost compilat pe LTSC 2019 cu entrypoint-ul Nuitka și un cache inițial gol. La testarea pe desktopul Windows au fost verificate cele șapte ecrane și titlurile, adăugarea, vânzarea, reaprovizionarea, ambele rapoarte, ștergerea și redeschiderea unei copii a CSV-ului. Fișierul original a rămas neschimbat.
