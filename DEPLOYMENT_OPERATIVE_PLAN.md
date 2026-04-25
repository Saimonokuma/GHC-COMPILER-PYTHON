# 🚀 GHC-COMPILER-PYTHON: DEPLOYMENT OPERATIVE PLAN v1.0
## Protocollo di Integrazione Finale su GitHub

Questo documento delinea i passi tecnici necessari per inizializzare, configurare e lanciare il progetto, garantendo l'incapsulamento steganografico dei binari Haskell in Python Wheels.

---

### **FASE 1: INIZIALIZZAZIONE DEL SUBSTRATO (REPOSITORY)**
1. **Creazione su GitHub**: Crea un nuovo repository chiamato `ghc-compiler-python`.
2. **Setup Locale**:
   ```bash
   git init ghc-compiler-python
   cd ghc-compiler-python
   mkdir -p src/ghc_compiler ghc-bindist/bin .github/workflows
   ```
3. **Ignora i Binari**: Crea un file `.gitignore` ma assicurati che Hatchling sia configurato (tramite il `pyproject.toml` già fornito) per includere i binari nonostante il gitignore.

---

### **FASE 2: IMPLEMENTAZIONE DEI COMPONENTI CORE**
1. **Packaging**: Inserisci il file `pyproject.toml` nella root. Questo utilizzerà `hatchling` per mappare i binari nella directory `.data/scripts` del Wheel.
2. **Wrapper Sterile**: Inserisci il codice in `src/ghc_compiler/__init__.py`. Questo gestirà l'isolamento ambientale (rimozione di `GHC_PACKAGE_PATH`) e il controllo del linker C (`gcc`/`clang`) sul sistema host.
3. **Metadata**: Crea un file `src/ghc_compiler/__about__.py` per gestire la versione (es. `__version__ = "9.4.8"`).

---

### **FASE 3: AUTOMAZIONE DEL PAYLOAD (SCRIPTS)**
Crea ed esegui localmente (o lascia che GitHub Actions lo faccia) gli script di gestione binari:
1. **`fetch_binaries.sh`**: Per scaricare GHC e Cabal e verificarne i checksum SHA-256.
2. **`optimize_binaries.sh`**: Per eseguire lo stripping dei simboli (`strip --strip-unneeded`) e ridurre la dimensione del Wheel fino al 90%.

---

### **FASE 4: ORCHESTRAZIONE CI/CD (GITHUB ACTIONS)**
Inserisci il file `.github/workflows/build.yml`. Questo è il cuore del sistema e deve:
1. Eseguire una matrice su **Ubuntu, macOS e Windows**.
2. Utilizzare `actions/cache` per memorizzare i binari GHC (spesso >500MB) ed evitare timeout.
3. Eseguire la "riparazione" del Wheel tramite `auditwheel` (Linux) e `delocate` (macOS) per includere le dipendenze C come `libgmp`.

---

### **FASE 5: VALIDAZIONE E2E (END-TO-END)**
Prima del rilascio, il workflow deve:
1. Creare un ambiente virtuale (`venv`) pulito.
2. Installare il Wheel appena generato.
3. Compilare un file `Main.hs` di test per confermare che il linker dell'host e il compilatore nel Venv dialoghino correttamente.

---

### **FASE 6: TRUSTED PUBLISHING (PYPI OIDC)**
1. **Configurazione PyPI**: Vai su PyPI e aggiungi GitHub come "Trusted Publisher" per il tuo progetto.
2. **Permessi OIDC**: Nel workflow YAML, imposta `permissions: id-token: write` per permettere lo scambio di token crittografici zero-trust tra GitHub e PyPI.
3. **Rilascio**: Esegui il push di un tag (es. `v9.4.8`) per innescare il caricamento automatico su PyPI.

---

**Sovereign Status**: *READY FOR EXECUTION* ⚜️
