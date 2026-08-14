"""
Valorant Tracker.gg Scraper — Approche API interne
═══════════════════════════════════════════════════
Stratégie :
  1. undetected-chromedriver ouvre tracker.gg UNE SEULE FOIS pour passer
     le challenge Cloudflare et récupérer le cookie cf_clearance.
  2. curl-cffi (imitation TLS Chrome) utilise ce cookie pour appeler
     directement les endpoints JSON internes de tracker.gg.
  → Pas de scraping HTML, données propres en JSON, zéro blocage Cloudflare.

Endpoints internes découverts via DevTools (F12 → Réseau → XHR) :
  • Profil / overview : api.tracker.gg/api/v2/valorant/standard/profile/riot/{player}
  • Liste des matchs  : api.tracker.gg/api/v2/valorant/standard/matches/riot/{player}
  • Détail d'un match : api.tracker.gg/api/v2/valorant/standard/matches/{matchId}
"""

import time
import json
import random
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── Selenium / undetected-chromedriver (pour récupérer cf_clearance) ──────────
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ── curl-cffi (pour appeler l'API avec le cookie Cloudflare) ──────────────────
from curl_cffi import requests as cf_requests


# ─────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────
PLAYER        = "Flex%232112"        # Riot ID encodé (# → %23)
PLAYER_LABEL  = "Flex#2112"         # Affiché dans les logs
BASE_API      = "https://api.tracker.gg/api/v2/valorant/standard"
TRACKER_HOME  = "https://tracker.gg/valorant"

MAX_MATCHES   = 20                   # Nombre de matchs à récupérer (None = tous)
CF_WAIT       = 15                   # Secondes pour laisser Cloudflare se résoudre


# ─────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────
@dataclass
class OverviewStats:
    rank: str = ""
    rating: str = ""
    peak_rank: str = ""
    win_rate: str = ""
    wins: str = ""
    losses: str = ""
    kd_ratio: str = ""
    kills: str = ""
    deaths: str = ""
    assists: str = ""
    acs: str = ""
    headshot_pct: str = ""
    damage_per_round: str = ""
    matches_played: str = ""

@dataclass
class MatchSummary:
    match_id: str = ""
    date: str = ""
    map: str = ""
    agent: str = ""
    result: str = ""
    score: str = ""
    kills: str = ""
    deaths: str = ""
    assists: str = ""
    kd_ratio: str = ""
    acs: str = ""
    headshot_pct: str = ""
    damage_per_round: str = ""
    duration: str = ""

@dataclass
class PlayerStats:
    name: str = ""
    agent: str = ""
    rank: str = ""
    kills: str = ""
    deaths: str = ""
    assists: str = ""
    kd_ratio: str = ""
    acs: str = ""
    headshot_pct: str = ""
    damage_per_round: str = ""
    first_bloods: str = ""
    plants: str = ""
    defuses: str = ""

@dataclass
class MatchDetail:
    match_id: str = ""
    map: str = ""
    date: str = ""
    result: str = ""
    score: str = ""
    duration: str = ""
    team_a: list = field(default_factory=list)
    team_b: list = field(default_factory=list)


# ─────────────────────────────────────────────
#  Étape 1 — Récupérer cf_clearance via uc
# ─────────────────────────────────────────────
def get_cloudflare_cookie() -> tuple[str, str]:
    """
    Ouvre tracker.gg avec undetected-chromedriver, attend que Cloudflare
    valide la session, puis extrait :
      - le cookie cf_clearance
      - le User-Agent du navigateur (doit correspondre exactement)

    Retourne (cf_clearance, user_agent).
    """
    print("\n[1/4] Ouverture du navigateur pour passer Cloudflare...")
    print("      (la fenêtre va s'ouvrir, ne la fermez pas)\n")

    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=fr-FR")
    options.add_argument("--disable-notifications")
    options.headless = False   # patch compatibilité
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = uc.Chrome(options=options, use_subprocess=True, version_main=151)

    try:
        driver.get(TRACKER_HOME)

        # Attendre que Cloudflare passe (disparition du challenge)
        print(f"      Attente de la validation Cloudflare ({CF_WAIT}s max)...")
        deadline = time.time() + CF_WAIT
        while time.time() < deadline:
            cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
            if "cf_clearance" in cookies:
                break
            time.sleep(1)
        else:
            # Toujours pas de cookie → donner la main à l'utilisateur
            print("\n  ⚠️  Cloudflare non résolu automatiquement.")
            print("  ➜  Complète le challenge dans la fenêtre Chrome si nécessaire.")
            print("  ➜  Le script attend (max 90s)...\n")
            deadline2 = time.time() + 90
            while time.time() < deadline2:
                cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
                if "cf_clearance" in cookies:
                    break
                time.sleep(2)

        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        cf_clearance = cookies.get("cf_clearance", "")
        user_agent   = driver.execute_script("return navigator.userAgent")

        if cf_clearance:
            print(f"  ✅ cf_clearance obtenu : {cf_clearance[:30]}...")
        else:
            print("  ⚠️  cf_clearance non trouvé — les requêtes API risquent d'échouer")

        return cf_clearance, user_agent

    finally:
        # Fermeture propre du driver
        print("      Fermeture du navigateur...")
        try:
            # On appelle uniquement quit(). 
            # quit() se charge déjà d'arrêter le service et de fermer les processus.
            driver.quit()
        except Exception:
            # Si une erreur survient ici, on l'ignore car le but est juste de fermer
            pass
        
        print("      Navigateur fermé.\n")


# ─────────────────────────────────────────────
#  Étape 2 — Session curl-cffi avec cf_clearance
# ─────────────────────────────────────────────
def build_session(cf_clearance: str, user_agent: str) -> cf_requests.Session:
    """
    Construit une session curl-cffi qui imite Chrome au niveau TLS
    et injecte le cookie Cloudflare pour accéder à l'API sans blocage.
    """
    session = cf_requests.Session(impersonate="chrome")

    session.headers.update({
        "User-Agent":       user_agent,
        "Accept":           "application/json, text/plain, */*",
        "Accept-Language":  "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding":  "gzip, deflate, br",
        "Referer":          "https://tracker.gg/",
        "Origin":           "https://tracker.gg",
        "Connection":       "keep-alive",
        "Sec-Fetch-Dest":   "empty",
        "Sec-Fetch-Mode":   "cors",
        "Sec-Fetch-Site":   "same-site",
    })

    # Injecter le cookie Cloudflare
    session.cookies.set("cf_clearance", cf_clearance, domain=".tracker.gg")

    return session


def api_get(session: cf_requests.Session, url: str) -> Optional[dict]:
    """
    Appel GET vers l'API interne avec gestion des erreurs.
    Retourne le JSON parsé ou None en cas d'échec.
    """
    try:
        time.sleep(random.uniform(0.8, 1.8))   # délai humain entre requêtes
        resp = session.get(url, timeout=20)

        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            print(f"  ⚠️  Rate limit (429) — attente 10s...")
            time.sleep(10)
            return api_get(session, url)   # retry
        elif resp.status_code in (403, 1020):
            print(f"  ❌ Cloudflare bloque toujours ({resp.status_code}) — cf_clearance expiré ?")
            return None
        else:
            print(f"  ⚠️  HTTP {resp.status_code} sur {url}")
            return None

    except Exception as e:
        print(f"  ❌ Erreur requête : {e}")
        return None


# ─────────────────────────────────────────────
#  Parsers JSON → dataclasses
# ─────────────────────────────────────────────
def _stat(segments: list, stat_key: str, default: str = "") -> str:
    """Cherche une valeur dans les segments de stats tracker.gg."""
    for seg in segments:
        stats = seg.get("stats", {})
        if stat_key in stats:
            val = stats[stat_key]
            # Valeur peut être un dict {"value": ..., "displayValue": ...}
            if isinstance(val, dict):
                return str(val.get("displayValue", val.get("value", default)))
            return str(val)
    return default


def parse_overview(data: dict) -> OverviewStats:
    """Parse la réponse JSON du profil en OverviewStats."""
    stats = OverviewStats()
    if not data:
        return stats

    try:
        segments = data.get("data", {}).get("segments", [])

        # Trouver le segment "overview" ou "season"
        overview_segs = [s for s in segments if s.get("type") in ("overview", "season", "playlist")]
        if not overview_segs:
            overview_segs = segments   # fallback : prendre tous les segments

        # Rank depuis les métadonnées
        for seg in overview_segs:
            meta = seg.get("metadata", {})
            if meta.get("name") and not stats.rank:
                stats.rank = meta.get("name", "")

        # Stats depuis les champs standardisés
        stats.kd_ratio        = _stat(overview_segs, "kDRatio")
        stats.kills           = _stat(overview_segs, "kills")
        stats.deaths          = _stat(overview_segs, "deaths")
        stats.assists         = _stat(overview_segs, "assists")
        stats.win_rate        = _stat(overview_segs, "matchesWinPct")
        stats.wins            = _stat(overview_segs, "matchesWon")
        stats.losses          = _stat(overview_segs, "matchesLost")
        stats.acs             = _stat(overview_segs, "scorePerRound")
        stats.headshot_pct    = _stat(overview_segs, "headshotsPercentage")
        stats.damage_per_round= _stat(overview_segs, "damagePerRound")
        stats.matches_played  = _stat(overview_segs, "matchesPlayed")

        # Rank complet (ex: "Gold 2")
        for seg in overview_segs:
            s = seg.get("stats", {})
            if "rank" in s:
                r = s["rank"]
                stats.rank   = r.get("metadata", {}).get("tierName", stats.rank)
                stats.rating = str(r.get("value", ""))
                break

    except Exception as e:
        print(f"  ⚠️  Erreur parse overview : {e}")

    return stats


def parse_matches(data: dict, max_matches: Optional[int] = None) -> list[MatchSummary]:
    """Parse la réponse JSON des matchs en liste de MatchSummary."""
    matches = []
    if not data:
        return matches

    try:
        items = data.get("data", {}).get("matches", data.get("data", []))
        if isinstance(items, dict):
            items = items.get("items", [])

        for i, item in enumerate(items):
            if max_matches and i >= max_matches:
                break

            m = MatchSummary()
            m.match_id = str(item.get("attributes", {}).get("id", i))

            metadata = item.get("metadata", {})
            m.date     = metadata.get("timestamp", metadata.get("date", ""))
            m.map      = metadata.get("mapName", "")
            m.result   = metadata.get("result", "")
            m.duration = metadata.get("duration", "")

            # Stats du joueur dans ce match
            segs = item.get("segments", [])
            player_seg = next(
                (s for s in segs if s.get("type") == "general"), segs[0] if segs else {}
            )
            s = player_seg.get("stats", {})

            def dv(key):
                v = s.get(key, {})
                return str(v.get("displayValue", v.get("value", ""))) if isinstance(v, dict) else str(v)

            m.agent            = player_seg.get("metadata", {}).get("agentName", "")
            m.kills            = dv("kills")
            m.deaths           = dv("deaths")
            m.assists          = dv("assists")
            m.kd_ratio         = dv("kDRatio")
            m.acs              = dv("scorePerRound")
            m.headshot_pct     = dv("headshotsPercentage")
            m.damage_per_round = dv("damagePerRound")

            # Score (ex: "13-7")
            rounds_won  = dv("roundsWon")
            rounds_lost = dv("roundsLost")
            if rounds_won and rounds_lost:
                m.score = f"{rounds_won}-{rounds_lost}"

            matches.append(m)

    except Exception as e:
        print(f"  ⚠️  Erreur parse matches : {e}")

    return matches


def filter_today_matches(matches: list[MatchSummary],
                         target_date: Optional[str] = None) -> list[MatchSummary]:
    """
    Filtre les matchs pour ne garder que ceux joués aujourd'hui (ou à target_date).

    tracker.gg retourne les dates en ISO 8601 (ex: "2026-04-16T14:32:07.000Z")
    que l'on compare au format "Apr 16" affiché sur le site.

    target_date : "YYYY-MM-DD" ou None (= date du jour automatique)
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    today = datetime.strptime(target_date, "%Y-%m-%d").date()

    filtered = []
    for m in matches:
        if not m.date:
            continue
        try:
            # Formats possibles : ISO "2026-04-16T14:32:07Z" ou "2026-04-16"
            date_str = m.date.replace("Z", "+00:00")
            match_date = datetime.fromisoformat(date_str).date()
        except ValueError:
            try:
                # Fallback : "Apr 16, 2026" ou variantes
                match_date = datetime.strptime(m.date[:10], "%Y-%m-%d").date()
            except ValueError:
                continue

        if match_date == today:
            filtered.append(m)

    return filtered


def parse_match_detail(data: dict, match_id: str) -> MatchDetail:
    """Parse la réponse JSON d'un match en MatchDetail (scorecard complet)."""
    detail = MatchDetail(match_id=match_id)
    if not data:
        return detail

    try:
        match_data = data.get("data", {})
        metadata   = match_data.get("metadata", {})

        detail.map      = metadata.get("mapName", "")
        detail.date     = metadata.get("timestamp", "")
        detail.duration = metadata.get("duration", "")

        # Segments = un par joueur
        segments = match_data.get("segments", [])

        team_map: dict[str, list] = {}

        for seg in segments:
            if seg.get("type") != "player":
                continue

            meta = seg.get("metadata", {})
            s    = seg.get("stats", {})

            def dv(key):
                v = s.get(key, {})
                return str(v.get("displayValue", v.get("value", ""))) if isinstance(v, dict) else str(v)

            p = PlayerStats(
                name             = meta.get("platformUserHandle", meta.get("playerName", "")),
                agent            = meta.get("agentName", ""),
                rank             = meta.get("tierName", ""),
                kills            = dv("kills"),
                deaths           = dv("deaths"),
                assists          = dv("assists"),
                kd_ratio         = dv("kDRatio"),
                acs              = dv("scorePerRound"),
                headshot_pct     = dv("headshotsPercentage"),
                damage_per_round = dv("damagePerRound"),
                first_bloods     = dv("firstBloods"),
                plants           = dv("plants"),
                defuses          = dv("defuses"),
            )

            team_id = str(meta.get("teamId", meta.get("team", "A")))
            team_map.setdefault(team_id, []).append(asdict(p))

            # Récupérer le score global depuis le premier joueur
            if not detail.result:
                detail.result = meta.get("result", "")
            if not detail.score:
                rw = dv("roundsWon")
                rl = dv("roundsLost")
                if rw and rl:
                    detail.score = f"{rw}-{rl}"

        teams = list(team_map.values())
        detail.team_a = teams[0] if len(teams) > 0 else []
        detail.team_b = teams[1] if len(teams) > 1 else []

    except Exception as e:
        print(f"  ⚠️  Erreur parse match detail : {e}")

    return detail


# ─────────────────────────────────────────────
#  Fonctions de scraping principales
# ─────────────────────────────────────────────
def scrape_overview(session: cf_requests.Session) -> OverviewStats:
    """Récupère et parse les stats overview du profil."""
    print("[2/4] Récupération du profil overview...")
    url  = f"{BASE_API}/profile/riot/{PLAYER}"
    data = api_get(session, url)

    if data:
        stats = parse_overview(data)
        print(f"  ✅ Rank: {stats.rank} | KD: {stats.kd_ratio} | Win%: {stats.win_rate}")
        return stats
    else:
        print("  ❌ Impossible de récupérer le profil")
        return OverviewStats()


def scrape_matches(session: cf_requests.Session,
                   max_matches: Optional[int] = MAX_MATCHES,
                   today_only: bool = False) -> list[MatchSummary]:
    """
    Récupère et parse la liste des matchs compétitifs.
    Si today_only=True, ne retourne que les matchs du jour (comme l'affichage
    "Apr 16" sur tracker.gg).
    """
    label = "matchs du jour" if today_only else f"{max_matches or 'tous les'} matchs compétitifs"
    print(f"\n[3/4] Récupération des {label}...")

    # Si on veut les matchs du jour, on récupère plus de résultats pour
    # être sûr d'avoir toute la journée (un joueur peut faire 10+ parties/jour)
    fetch_limit = None if today_only else max_matches
    url  = f"{BASE_API}/matches/riot/{PLAYER}?type=competitive"
    data = api_get(session, url)

    if not data:
        print("  ❌ Impossible de récupérer les matchs")
        return []

    matches = parse_matches(data, fetch_limit)

    if today_only:
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_label = datetime.now().strftime("%b %-d") if hasattr(datetime, "_") else datetime.now().strftime("%b %d").lstrip("0")
        # Format "Apr 16" comme tracker.gg
        today_label = datetime.now().strftime("%b") + " " + str(datetime.now().day)
        matches = filter_today_matches(matches, today_str)
        print(f"  📅 Filtre date du jour : {today_label} ({today_str})")
        print(f"  ✅ {len(matches)} match(s) trouvé(s) aujourd'hui")
    else:
        print(f"  ✅ {len(matches)} matchs récupérés")

    for i, m in enumerate(matches[:10]):
        print(f"     [{i+1}] {m.date[:10]} | {m.map:<12} | {m.result:<8} | "
              f"{m.score:<6} | KDA {m.kills}/{m.deaths}/{m.assists}")

    return matches


def scrape_match_detail(session: cf_requests.Session, match_id: str) -> MatchDetail:
    """Récupère et parse le scorecard complet d'un match."""
    url  = f"{BASE_API}/matches/{match_id}"
    data = api_get(session, url)

    if data:
        detail = parse_match_detail(data, match_id)
        print(f"  ✅ {detail.map} | {detail.result} | {detail.score} "
              f"| {len(detail.team_a) + len(detail.team_b)} joueurs")
        return detail
    else:
        print(f"  ❌ Impossible de récupérer le match {match_id}")
        return MatchDetail(match_id=match_id)


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Valorant Tracker.gg Scraper — API interne + curl-cffi")
    print(f"  Profil : {PLAYER_LABEL}")
    print("=" * 60)

    results = {
        "profile":       PLAYER_LABEL,
        "overview":      {},
        "matches":       [],
        "match_details": [],
    }

    # ── 1. Passer Cloudflare une seule fois ──────────────────────
    cf_clearance, user_agent = get_cloudflare_cookie()

    if not cf_clearance:
        print("❌ Impossible d'obtenir le cookie Cloudflare. Arrêt.")
        return

    # ── 2. Construire la session API ────────────────────────────
    session = build_session(cf_clearance, user_agent)

    try:
        # ── 3. Overview ─────────────────────────────────────────
        overview = scrape_overview(session)
        results["overview"] = asdict(overview)

        # ── 4. Liste des matchs ──────────────────────────────────
        # TODAY_ONLY = True  → uniquement les matchs du jour (comme "Apr 16" sur tracker.gg)
        # TODAY_ONLY = False → tous les matchs (limité à MAX_MATCHES)
        TODAY_ONLY = False

        matches = scrape_matches(session, max_matches=MAX_MATCHES, today_only=TODAY_ONLY)
        results["matches"] = [asdict(m) for m in matches]
        results["date_filtre"] = datetime.now().strftime("%Y-%m-%d") if TODAY_ONLY else "all"

        if not matches:
            print(f"  ℹ️  Aucun match trouvé pour aujourd'hui ({datetime.now().strftime('%b %-d' if False else '%b %d').lstrip('0')})")

        # ── 5. Détail de TOUS les matchs du jour (ou des 3 premiers si all) ──
        detail_limit = len(matches) if TODAY_ONLY else min(3, len(matches))
        print(f"\n[4/4] Récupération du détail des {detail_limit} match(s)...")
        for i, match in enumerate(matches[:detail_limit]):
            if not match.match_id:
                continue
            print(f"  Partie {i+1}/{detail_limit} : {match.match_id}")
            detail = scrape_match_detail(session, match.match_id)
            results["match_details"].append(asdict(detail))

        # ── Sauvegarde JSON ──────────────────────────────────────
        output_file = f"valorant_stats_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n{'=' * 60}")
        print(f"  ✅ Données sauvegardées → {output_file}")
        print(f"     Overview  : {len(results['overview'])} champs")
        print(f"     Matchs    : {len(results['matches'])} résultats")
        print(f"     Détails   : {len(results['match_details'])} scorecards")
        print(f"{'=' * 60}")

        print("\n─── OVERVIEW ───────────────────────────────────────────")
        for k, v in results["overview"].items():
            if v and v not in ("", "N/A"):
                print(f"  {k:<22} : {v}")

        date_label = datetime.now().strftime("%b") + " " + str(datetime.now().day)
        titre = f"MATCHS DU JOUR ({date_label})" if TODAY_ONLY else "DERNIÈRES PARTIES"
        print(f"\n─── {titre} {'─' * (49 - len(titre))}")
        if results["matches"]:
            for m in results["matches"]:
                result_icon = "✅" if "win" in m["result"].lower() or "victory" in m["result"].lower() else "❌"
                print(f"  {result_icon} {m['date'][11:16]} | {m['map']:<12} | "
                      f"{m['result']:<8} | {m['score']:<6} | "
                      f"KDA {m['kills']}/{m['deaths']}/{m['assists']} | ACS {m['acs']}")
        else:
            print(f"  Aucun match joué aujourd'hui ({date_label})")

    except KeyboardInterrupt:
        print("\n⚠️  Interrompu par l'utilisateur")

    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()