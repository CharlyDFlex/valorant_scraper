# 🎯 Valorant Tracker.gg Scraper

Scraper Python basé sur **Selenium** pour extraire automatiquement les statistiques Valorant depuis [tracker.gg](https://tracker.gg) — overview competitive, historique des parties, et scorecard détaillé par match.

---

## 📋 Table des matières

- [Fonctionnalités](#-fonctionnalités)
- [Prérequis](#-prérequis)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Utilisation](#-utilisation)
- [Structure des données](#-structure-des-données)
- [Dépannage](#-dépannage)
- [Limitations & conseils](#-limitations--conseils)

---

## ✨ Fonctionnalités

| Module | Ce qui est extrait |
|---|---|
| **Overview** | Rank, rating, peak rank, KD, win rate, ACS, headshot %, damage/round |
| **Liste des parties** | Map, agent, résultat, score, KDA, ACS, date, durée |
| **Détail par partie** | Scorecard complet des 10 joueurs avec toutes les stats |

Le script gère automatiquement :
- ✅ Le scroll infini pour charger l'historique complet
- ✅ Le clic sur une partie et la navigation vers le détail
- ✅ L'export JSON structuré
- ✅ Les options anti-détection basiques (User-Agent, masquage webdriver)

---

## 🔧 Prérequis

| Outil | Version minimale |
|---|---|
| Python | 3.10+ |
| Google Chrome | Dernière version stable |
| ChromeDriver | Correspondant à votre version de Chrome |

> **Vérifier votre version de Chrome :** ouvrir Chrome → `chrome://settings/help`

---

## 📦 Installation

### 1. Cloner / télécharger le projet

```bash
# Si vous avez Git
git clone https://github.com/CharlyDFlex/valorant-scraper.git
cd valorant-scraper

# Ou simplement placer valorant_scraper.py dans un dossier dédié
```

### 2. Créer un environnement virtuel (recommandé)

```bash
# Créer l'environnement
python -m venv venv

# Activer (Windows)
venv\Scripts\activate

# Activer (macOS / Linux)
source venv/bin/activate
```

### 3. Installer les dépendances

**Option A — avec `webdriver-manager` (recommandé, gère ChromeDriver automatiquement)**

```bash
pip install selenium webdriver-manager
```

Puis modifier le début de `main()` dans le script :

```python
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# Remplacer :
driver = create_driver()

# Par :
def create_driver(headless=False):
    options = Options()
    # ... (garder toutes les options existantes)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver
```

**Option B — avec ChromeDriver manuel**

1. Télécharger ChromeDriver sur [chromedriver.chromium.org](https://chromedriver.chromium.org/downloads) en choisissant la version qui correspond à votre Chrome
2. Placer l'exécutable dans le dossier du projet (ou dans votre `PATH`)

```bash
pip install selenium
```

---

## ⚙️ Configuration

Ouvrir `valorant_scraper.py` et modifier les constantes en haut du fichier :

```python
# ─── Profil à scraper ─────────────────────────────────────
PROFILE_URL = (
    "https://tracker.gg/valorant/profile/riot/Flex%232112/overview"
    "?platform=pc&playlist=competitive"
)
MATCHES_URL = (
    "https://tracker.gg/valorant/profile/riot/Flex%232112/matches"
    "?platform=pc&playlist=competitive"
)

# ─── Réglages ─────────────────────────────────────────────
WAIT_TIMEOUT = 15    # Délai d'attente max pour charger un élément (secondes)
SCROLL_PAUSE  = 1.5  # Pause entre chaque scroll (secondes)
MAX_MATCHES   = 20   # Nombre max de parties à scraper (None = toutes)
```

> **Pour changer de profil :** remplacer `Flex%232112` par `PseudoRiot%23Tag` dans les deux URLs.  
> Le `#` doit être encodé en `%23`. Exemple : `MonPseudo#1234` → `MonPseudo%231234`

---

## 🚀 Utilisation

### Lancement standard

```bash
python valorant_scraper.py
```

Une fenêtre Chrome s'ouvre, le script navigue automatiquement entre les pages et affiche la progression dans le terminal.

### Lancement en mode headless (sans fenêtre)

Modifier la ligne dans `main()` :

```python
# Changer headless=False en headless=True
driver = create_driver(headless=True)
```

### Scraper uniquement le détail d'une partie spécifique

```python
# En bas du script, dans main(), appeler directement :
detail = scrape_match_detail(driver, "ID_DU_MATCH")
```

L'ID du match se trouve dans l'URL d'une partie :  
`https://tracker.gg/valorant/match/`**`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`**

### Scraper en cliquant sur une partie depuis la liste

```python
# Clique sur la 1ère partie de la liste (index 0)
detail = click_and_scrape_match(driver, match_index=0)

# Clique sur la 3ème partie
detail = click_and_scrape_match(driver, match_index=2)
```

---

## 📁 Structure des données

Le script génère un fichier `valorant_stats.json` avec la structure suivante :

```json
{
  "profile": "Flex#2112",

  "overview": {
    "rank": "Gold 2",
    "rating": "1234",
    "peak_rank": "Platinum 1",
    "win_rate": "52%",
    "wins": "130",
    "losses": "120",
    "kd_ratio": "1.12",
    "kills": "18.4",
    "deaths": "16.4",
    "assists": "5.2",
    "acs": "215",
    "headshot_pct": "23%",
    "damage_per_round": "148",
    "matches_played": "250"
  },

  "matches": [
    {
      "match_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "date": "Today 14:32",
      "map": "Ascent",
      "agent": "Jett",
      "result": "Victory",
      "score": "13-7",
      "kills": "22",
      "deaths": "14",
      "assists": "4",
      "kd_ratio": "1.57",
      "acs": "267",
      "headshot_pct": "28%",
      "damage_per_round": "175",
      "duration": "38:12"
    }
  ],

  "match_details": [
    {
      "match_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "map": "Ascent",
      "date": "Today 14:32",
      "result": "Victory",
      "score": "13-7",
      "duration": "38:12",
      "team_a": [
        {
          "name": "Flex#2112",
          "agent": "Jett",
          "rank": "Gold 2",
          "kills": "22",
          "deaths": "14",
          "assists": "4",
          "kd_ratio": "1.57",
          "acs": "267",
          "headshot_pct": "28%",
          "damage_per_round": "175",
          "first_bloods": "3",
          "plants": "1",
          "defuses": "0"
        }
      ],
      "team_b": []
    }
  ]
}
```

---

## 🐛 Dépannage

### ❌ `SessionNotCreatedException` — ChromeDriver ne correspond pas à Chrome

```
Message: session not created: This version of ChromeDriver only supports Chrome version XX
```

**Solution :** utiliser `webdriver-manager` (voir [Installation](#-installation), Option A) ou télécharger la bonne version de ChromeDriver.

---

### ❌ Les éléments ne sont pas trouvés / données vides

tracker.gg est un site à fort rendu JavaScript. Si les données ne sont pas scrappées :

1. Augmenter `WAIT_TIMEOUT` et `SCROLL_PAUSE`
2. Passer en mode `headless=False` pour observer le comportement
3. tracker.gg peut avoir mis à jour ses sélecteurs CSS — inspecter la page avec F12 et adapter les sélecteurs dans le script

---

### ❌ Blocage Cloudflare / page blanche

tracker.gg utilise Cloudflare. En cas de blocage :

```bash
pip install undetected-chromedriver
```

Puis remplacer dans le script :

```python
# Avant
from selenium import webdriver
driver = webdriver.Chrome(options=options)

# Après
import undetected_chromedriver as uc
driver = uc.Chrome(options=options)
```

---

### ❌ `ModuleNotFoundError: No module named 'selenium'`

```bash
pip install selenium
# ou
pip3 install selenium
```

Vérifier que l'environnement virtuel est bien activé si vous en utilisez un.

---

### ❌ `PermissionError` sur Windows avec ChromeDriver

Placer `chromedriver.exe` dans le même dossier que le script, ou l'ajouter dans les variables d'environnement système (`PATH`).

---

## ⚠️ Limitations & conseils

- **Respect du site :** ne pas lancer le script trop fréquemment. Ajouter des pauses entre les requêtes pour éviter de surcharger les serveurs.
- **Données dynamiques :** tracker.gg charge les stats en JavaScript. Si une stat est manquante, inspecter le DOM (F12) et adapter le sélecteur CSS correspondant.
- **Anti-bot :** en cas de CAPTCHA ou de blocage répété, espacer les lancements ou utiliser `undetected-chromedriver`.

---

## 📂 Arborescence du projet

```
valorant-scraper/
├── valorant_scraper.py   # Script principal
├── README.md             # Ce fichier
├── valorant_stats.json   # Généré après exécution
└── venv/                 # Environnement virtuel (si créé)
└── valorant_stats_x_x    # Fichier exemple basé sur mon compte
```

---

> Projet à usage personnel. Consulter les [CGU de tracker.gg](https://tracker.gg/legal) avant toute utilisation intensive ou commerciale.
