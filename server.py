from flask import Flask, jsonify, request
from garminconnect import Garmin, GarminConnectAuthenticationError
from garth.exc import GarthHTTPError
from datetime import date, datetime, timedelta
from pathlib import Path
import logging
import sys

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

TOKEN_DIR      = Path('/root/.garminconnect')
EMAIL_SECRET   = Path('/run/secrets/garmin_email')
PASSWORD_SECRET = Path('/run/secrets/garmin_password')

# ── App ───────────────────────────────────────────────────────────────────────

app = Flask(__name__)
client: Garmin | None = None


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _load_credentials() -> tuple[str, str]:
    """Read email + password from Docker secrets."""
    email    = EMAIL_SECRET.read_text().strip()
    password = PASSWORD_SECRET.read_text().strip()
    return email, password


def _login_with_tokens(garmin: Garmin) -> bool:
    """Try to resume session from saved tokens. Returns True on success."""
    try:
        garmin.login(str(TOKEN_DIR))
        log.info("Tokens geladen — gebruiker: %s", garmin.display_name)
        return True
    except Exception as e:
        log.warning("Token login mislukt: %s", e)
        return False


def _login_with_credentials() -> Garmin | None:
    """
    Full credential login with MFA support.
    Saves fresh tokens on success so the next restart uses token login.
    """
    try:
        email, password = _load_credentials()
    except Exception as e:
        log.error("Kan credentials niet lezen: %s", e)
        return None

    garmin = Garmin(email=email, password=password, is_cn=False, return_on_mfa=True)

    try:
        result, mfa_data = garmin.login()
    except GarminConnectAuthenticationError as e:
        log.error("Authenticatie mislukt: %s", e)
        return None
    except Exception as e:
        log.error("Login fout: %s", e)
        return None

    if result == "needs_mfa":
        log.info("MFA vereist — voer de code in die Garmin naar je e-mail stuurde.")
        try:
            mfa_code = input("MFA code: ").strip()
            garmin.resume_login(mfa_data, mfa_code)
        except GarthHTTPError as e:
            err = str(e)
            if "429" in err:
                log.error("Rate-limited door Garmin (429). Wacht even en herstart.")
            elif any(c in err for c in ("401", "403")):
                log.error("MFA code onjuist (401/403).")
            else:
                log.error("MFA HTTP fout: %s", e)
            return None
        except Exception as e:
            log.error("MFA fout: %s", e)
            return None

    # Sla tokens op voor volgende herstart
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    garmin.garth.dump(str(TOKEN_DIR))
    log.info("Credentials login OK — tokens opgeslagen. Gebruiker: %s", garmin.display_name)
    return garmin


def init_garmin() -> None:
    """
    Initialiseer de Garmin client.
    Probeert eerst opgeslagen tokens; valt terug op credential login.
    """
    global client

    # Stap 1: probeer tokens
    if TOKEN_DIR.exists() and any(TOKEN_DIR.glob("*.json")):
        g = Garmin()
        if _login_with_tokens(g):
            client = g
            return

    # Stap 2: volledige login
    log.info("Geen geldige tokens — volledige login starten.")
    g = _login_with_credentials()
    if g:
        client = g
    else:
        log.error("Garmin initialisatie mislukt — alle endpoints geven 503 terug.")


# ── Decorator: client vereist ─────────────────────────────────────────────────

from functools import wraps

def requires_client(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if client is None:
            return jsonify({'error': 'Niet verbonden met Garmin Connect'}), 503
        try:
            return f(*args, **kwargs)
        except GarthHTTPError as e:
            err = str(e)
            if "401" in err or "403" in err:
                return jsonify({'error': 'Sessie verlopen — herstart container'}), 401
            return jsonify({'error': str(e)}), 502
        except Exception as e:
            log.error("Fout in %s: %s", f.__name__, e)
            return jsonify({'error': str(e)}), 500
    return wrapper


# ── Hulpfunctie: datumparameter ───────────────────────────────────────────────

def get_datum(default: str | None = None) -> str:
    """Haal ?datum= op; standaard vandaag."""
    return request.args.get('datum', default or date.today().isoformat())


# ── Beheer-routes ─────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    return jsonify({
        'status':   'ok',
        'ingelogd': client is not None,
        'gebruiker': client.display_name if client else None,
        'datum':    date.today().isoformat(),
    })


@app.route('/herverbind', methods=['POST'])
def herverbind():
    """Forceer een nieuwe login (bijv. na verlopen sessie)."""
    init_garmin()
    return jsonify({'ingelogd': client is not None})


# ── Basis gezondheidsdata ─────────────────────────────────────────────────────

@app.route('/activiteiten')
@requires_client
def activiteiten():
    start = request.args.get('start', 0, type=int)
    limit = request.args.get('limit', 10, type=int)
    return jsonify(client.get_activities(start, limit))


@app.route('/stappen')
@requires_client
def stappen():
    return jsonify(client.get_steps_data(get_datum()))


@app.route('/slaap')
@requires_client
def slaap():
    return jsonify(client.get_sleep_data(get_datum()))


@app.route('/hartslag')
@requires_client
def hartslag():
    return jsonify(client.get_heart_rates(get_datum()))


@app.route('/hrv')
@requires_client
def hrv():
    return jsonify(client.get_hrv_data(get_datum()))


@app.route('/stress')
@requires_client
def stress():
    return jsonify(client.get_stress_data(get_datum()))


@app.route('/stats')
@requires_client
def stats():
    return jsonify(client.get_stats(get_datum()))


@app.route('/gewicht')
@requires_client
def gewicht():
    datum = request.args.get('datum')
    if datum:
        return jsonify(client.get_weigh_ins(datum, datum))
    start = request.args.get('start', '2024-01-01')
    eind  = request.args.get('eind',  date.today().isoformat())
    return jsonify(client.get_body_composition(start, eind))


# ── Training & prestaties ─────────────────────────────────────────────────────

@app.route('/training-readiness')
@requires_client
def training_readiness():
    """Training Readiness score 0-100 + status + feedback."""
    return jsonify(client.get_training_readiness(get_datum()))


@app.route('/training-status')
@requires_client
def training_status():
    """Training Status (Productive / Maintaining / Overreaching etc.)"""
    return jsonify(client.get_training_status(get_datum()))


@app.route('/vo2max')
@requires_client
def vo2max():
    """
    VO2max + fitness age. Ondersteunt:
      ?datum=YYYY-MM-DD          → één dag
      ?startDatum=&eindDatum=    → datumreeks
      (geen params)              → vandaag
    """
    datum       = request.args.get('datum')
    start_datum = request.args.get('startDatum')
    eind_datum  = request.args.get('eindDatum')
    resultaten  = []

    def _fetch(ds: str):
        try:
            return {'calendarDate': ds, 'data': client.get_max_metrics(ds)}
        except Exception as e:
            return {'calendarDate': ds, 'error': str(e)}

    if datum:
        resultaten.append(_fetch(datum))
    elif start_datum and eind_datum:
        s = datetime.strptime(start_datum, '%Y-%m-%d').date()
        e = datetime.strptime(eind_datum,  '%Y-%m-%d').date()
        while s <= e:
            resultaten.append(_fetch(s.isoformat()))
            s += timedelta(days=1)
    else:
        resultaten.append(_fetch(date.today().isoformat()))

    return jsonify(resultaten)


@app.route('/race-predictions')
@requires_client
def race_predictions():
    """Voorspelde race tijden: 5K / 10K / HM / Marathon."""
    return jsonify(client.get_race_predictions())


@app.route('/hartslagzones')
@requires_client
def hartslagzones():
    """Dagelijkse hartslagzone-verdeling."""
    datum = get_datum()
    r     = client.get_heart_rates(datum)
    zones = r.get('heartRateZones', []) if isinstance(r, dict) else []
    return jsonify({'datum': datum, 'heartRateZones': zones, 'raw': r})


@app.route('/activiteit-zones')
@requires_client
def activiteit_zones():
    """HR zones voor één activiteit. Gebruik: ?id=<activityId>"""
    activity_id = request.args.get('id', type=int)
    if not activity_id:
        return jsonify({'error': 'id parameter verplicht'}), 400
    return jsonify(client.get_activity_hr_in_timezones(activity_id))


@app.route('/fitnessleeftijd')
@requires_client
def fitnessleeftijd():
    """Fitness Age."""
    return jsonify(client.get_fitnessage_data(get_datum()))


@app.route('/persoonlijke-records')
@requires_client
def persoonlijke_records():
    """Persoonlijke records per afstand/discipline."""
    return jsonify(client.get_personal_record())


@app.route('/workouts')
@requires_client
def workouts():
    """
    Geplande workouts uit Garmin Connect.
    Gebruik: /workouts?start=0&limit=20
    Geeft alle opgeslagen workouts terug inclusief stappen, duur en hartslagzones.
    """
    start = request.args.get('start', 0, type=int)
    limit = request.args.get('limit', 20, type=int)
    return jsonify(client.get_workouts(start, limit))


# ── Start ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_garmin()
    app.run(host='0.0.0.0', port=8080, debug=False)
