from flask import Flask, render_template, request, redirect, session, url_for
from datetime import datetime, timedelta
from flask_mysqldb import MySQL
import MySQLdb.cursors
import config

app = Flask(__name__) # Initialisiere Flask App
app.secret_key = 'secret_key' #Verschlüsselung für Sessions

# DB Config laden
app.config.from_object(config)

# MySQL initialisieren
mysql = MySQL(app)


@app.route('/', methods=['GET', 'POST'])# Login-Seite mit GET und POST
def login():
    if request.method == 'POST': # Wird abgefragt wenn der Nutzer das Formular absendet
        user = request.form['username'] # Nutzername aus dem Formular
        pw = request.form['password'] # Passwort aus dem Formular
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)# Cursor für Dictionary-Ergebnisse
        cursor.execute('SELECT * FROM benutzer WHERE benutzername = %s', (user,))# Suche nach Nutzer in der DB
        account = cursor.fetchone()# Eintrag in der DB, der dem Nutzer entspricht
        if account and account['passwort'] == pw:  # nur testweise – kein Hash, Prüfen ob Nutzer und Passwort übereinstimmen

            # Nutzer-Session setzen, um eingeloggten Zustand zu speichern
            session['loggedin'] = True 
            session['id'] = account['id']
            session['username'] = account['benutzername']

            if user == 'adminuser' and pw == 'adminuser123':# Admin-Login
                return redirect(url_for('kurs_anlegen'))# Weiterleitung zum Kurs anlegen für Admin
            return redirect(url_for('dashboard'))# Weiterleitung zum Dashboard für normale Nutzer
    return render_template('login.html')# Login-Seite rendern, wenn GET oder ungültige POST-Anfrage

@app.route('/register', methods=['GET', 'POST']) # Registrierung-Seite mit GET und POST
def register():
    if request.method == 'POST': # Wird abgefragt wenn der Nutzer das Formular absendet
        user = request.form['username'] # Nutzername aus dem Formular
        pw = request.form['password'] # Passwort aus dem Formular
        cursor = mysql.connection.cursor() # cursor für dictionary-Ergebnisse
        cursor.execute('INSERT INTO benutzer (benutzername, passwort) VALUES (%s, %s)', (user, pw)) #Nuterdaten in die DB einfügen
        mysql.connection.commit() # Änderungen in der DB speichern
        return redirect(url_for('login')) # Weiterleitung zur Login-Seite nach erfolgreicher Registrierung
    return render_template('register.html') # Registrierung-Seite rendern, wenn GET oder ungültige POST-Anfrage


@app.route('/dashboard', methods=['GET', 'POST']) # Dashboard-Seite mit GET und POST
def dashboard():
    if 'loggedin' not in session: # Prüfen ob der Nutzer eingeloggt ist
        return redirect(url_for('login')) # Weiterleitung zur Login-Seite, wenn nicht eingeloggt

    delta = int(request.args.get('woche', 0)) # Wochen-Offset aus der URL, Standard ist 0 (aktuelle Woche) | URL-Parameter ?wocche=1 für nächste Woche, ?woche=-1 für vorherige Woche
    heute = datetime.today()# Aktuelles Datum und Uhrzeit
    start_montag = heute - timedelta(days=heute.weekday()) + timedelta(weeks=delta) # Startdatum der Woche (Montag) berechnen, abhängig vom Wochen-Offset
    end_sonntag = start_montag + timedelta(days=6) # Enddatum der Woche (Sonntag) berechnen

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor) # Cursor für Dictionary-Ergebnisse
    cursor.execute('SELECT DISTINCT titel FROM kurse') # Alle Kurstitel aus der DB abfragen
    kurstitel = [row['titel'] for row in cursor.fetchall()] # Kurstitel in eine Liste umwandeln

    if kurstitel:
        gewaehlter_kurs = request.args.get('kurs') or kurstitel[0] # Gewählten Kurs aus der URL abfragen, Standard ist der erste Kurs in der Liste
    else:
        gewaehlter_kurs = None # Wenn keine Kurse vorhanden sind, ist der gewählte Kurs der Erste

    kurs = None # Wenn kein Kurs gewählt wurde, bleibt kurs None damit der nicht angezeigt wird

    if gewaehlter_kurs: # wenn einer gewählt wurde
        cursor.execute('SELECT * FROM kurse WHERE titel = %s', (gewaehlter_kurs,)) # Kursinformationen aus der DB abfragen
        kurs = cursor.fetchone() # Kursinformationen als Dictionary

        kurs_id = None # wenn kein gültiger Kurs gewählt wurde, bleibt kurs_id None damit keine Buchungen angezeigt werden und keine buchungen gemacht werden können
        if kurs and kurs['von_datum'] and kurs['bis_datum']: # Prüfen ob Kurs gültige Datumsangaben hat
            import datetime as dt
            von = kurs['von_datum'] # Startdatum des Kurses
            bis = kurs['bis_datum'] # Enddatum des Kurses
            if isinstance(von, str): # Wenn von ein String ist, in Datum umwandeln
                von = dt.datetime.strptime(von, '%Y-%m-%d').date()
            if isinstance(bis, str): # Wenn bis ein String ist, in Datum umwandeln
                bis = dt.datetime.strptime(bis, '%Y-%m-%d').date()
            if von <= end_sonntag.date() and bis >= start_montag.date(): # Prüfen ob der Kurs in der gewählten Woche liegt
                kurs_id = kurs['id'] # eindeutige Kurs-ID des Kurses wird in kurs_id gespeichert
        else:
            kurs = None # Wenn Kurs keine gültigen Datumsangaben hat, wird kurs auf None gesetzt, damit keine Buchungen angezeigt werden und keine buchungen gemacht werden können
    else:
        kurs_id = None # Wenn kein Kurs gewählt wurde, bleibt kurs_id None damit keine Buchungen angezeigt werden und keine buchungen gemacht werden können

    # Buchungen für die Woche laden (ohne max_teilnehmer, Block wieder aktiv)
    if kurs_id:
        cursor.execute('''
            SELECT * FROM buchungen WHERE kurs_id = %s AND datum BETWEEN %s AND %s
        ''', (kurs_id, start_montag.strftime('%Y-%m-%d'), end_sonntag.strftime('%Y-%m-%d')))
        buchungen = cursor.fetchall()
        # Eigene Buchungen
        cursor.execute('''
            SELECT * FROM buchungen WHERE kurs_id = %s AND benutzer_id = %s AND datum BETWEEN %s AND %s
        ''', (kurs_id, session['id'], start_montag.strftime('%Y-%m-%d'), end_sonntag.strftime('%Y-%m-%d')))
        eigene_buchungen = cursor.fetchall()
    else:
        buchungen = []
        eigene_buchungen = []
    # max_teilnehmer wird an das Template übergeben, damit die Anzeige und Logik im Template korrekt funktioniert
    if kurs_id:
        max_teilnehmer = kurs['max_teilnehmer'] if kurs and 'max_teilnehmer' in kurs else None
    else:
        max_teilnehmer = None
    # Dashboard-Template rendern (Rückgabe der View)
    return render_template('dashboard.html', start=start_montag.date(), delta=delta, timedelta=timedelta, 
                           kurstitel=kurstitel, gewaehlter_kurs=gewaehlter_kurs, buchungen=buchungen, eigene_buchungen=eigene_buchungen, kurs=kurs, max_teilnehmer=max_teilnehmer)

@app.route('/buchen', methods=['POST']) # Definiert die Route '/buchen' für POST-Anfragen
def buchen():
    if 'loggedin' not in session: # Prüft, ob der Nutzer eingeloggt ist
        return redirect(url_for('login')) # Wenn nicht, weiterleiten zur Login-Seite
    slots = request.json.get('slots', []) # Holt die ausgewählten Slots aus der JSON-Anfrage (Liste von Slots)
    kurs_titel = request.json.get('kurs') # Holt den Kurstitel aus der JSON-Anfrage
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor) # Erstellt einen Datenbank-Cursor für Dictionary-Ergebnisse
    cursor.execute('SELECT id, max_teilnehmer FROM kurse WHERE titel = %s', (kurs_titel,)) # Sucht die Kurs-ID zum angegebenen Kurstitel
    kurs = cursor.fetchone() # Holt das Ergebnis (Kurs-Datensatz) aus der Datenbank
    if not kurs: # Wenn kein Kurs gefunden wurde
        return {'status': 'error', 'msg': 'Kurs nicht gefunden'} # Fehler-Response zurückgeben
    kurs_id = kurs['id'] # Speichert die Kurs-ID für spätere Buchungen
    max_teilnehmer = kurs['max_teilnehmer'] # maximale Teilnehmeranzahl des Kurses
    errors = []
    for slot in slots: # Geht alle ausgewählten Slots durch
        datum = slot['datum'] # Holt das Datum des Slots
        stunde = slot['stunde'] # Holt die Stunde des Slots
        # Prüfen ob schon gebucht (für diesen User)
        cursor.execute('SELECT * FROM buchungen WHERE kurs_id = %s AND benutzer_id = %s AND datum = %s AND stunde = %s', (kurs_id, session['id'], datum, stunde)) # Prüft, ob der Nutzer diesen Slot schon gebucht hat
        if cursor.fetchone(): # Wenn bereits eine Buchung existiert
            errors.append({'datum': datum, 'stunde': stunde, 'msg': 'Du hast diesen Slot schon gebucht'})
            continue  # User hat diesen Slot schon gebucht, überspringen
        # Prüfen wie viele Buchungen es für diesen Slot schon gibt
        cursor.execute('SELECT COUNT(*) as cnt FROM buchungen WHERE kurs_id = %s AND datum = %s AND stunde = %s', (kurs_id, datum, stunde)) # Zählt die Anzahl der Buchungen für diesen Slot
        count = cursor.fetchone()['cnt'] # Anzahl der Buchungen
        if count >= max_teilnehmer: # Wenn die maximale Teilnehmeranzahl erreicht ist
            errors.append({'datum': datum, 'stunde': stunde, 'msg': 'Die maximale Teilnehmerzahl ist erreicht'})
            continue  # Slot ist voll, nicht mehr buchbar
        cursor.execute('INSERT INTO buchungen (kurs_id, benutzer_id, datum, stunde) VALUES (%s, %s, %s, %s)', (kurs_id, session['id'], datum, stunde)) # Fügt die Buchung in die Datenbank ein
    mysql.connection.commit() # Speichert alle Änderungen in der Datenbank
    if errors:
        return {'status': 'error', 'errors': errors}
    return {'status': 'ok'} # Gibt eine Erfolgs-Response zurück

@app.route('/kurs_anlegen', methods=['GET', 'POST']) # Definiert die Route '/kurs_anlegen' für GET und POST
def kurs_anlegen():
    if 'loggedin' not in session: # Prüft, ob der Nutzer eingeloggt ist
        return redirect(url_for('login')) # Wenn nicht, weiterleiten zur Login-Seite
    if request.method == 'POST': # Wenn das Formular abgeschickt wurde (POST)
        titel = request.form['titel'] # Holt den Kurstitel aus dem Formular
        beschreibung = request.form['beschreibung'] # Holt die Kursbeschreibung aus dem Formular
        von_datum = request.form['von_datum'] # Holt das Startdatum aus dem Formular
        bis_datum = request.form['bis_datum'] # Holt das Enddatum aus dem Formular
        max_teilnehmer = int(request.form['max_teilnehmer']) # Holt die maximale Teilnehmeranzahl aus dem Formular
        cursor = mysql.connection.cursor() # Erstellt einen Datenbank-Cursor
        cursor.execute('INSERT INTO kurse (titel, beschreibung, von_datum, bis_datum, max_teilnehmer) VALUES (%s, %s, %s, %s, %s)', (titel, beschreibung, von_datum, bis_datum, max_teilnehmer)) # Fügt den neuen Kurs in die Datenbank ein
        mysql.connection.commit() # Speichert die Änderungen in der Datenbank
        return redirect(url_for('dashboard')) # Nach dem Anlegen des Kurses weiterleiten zum Dashboard
    return render_template('kurs_anlegen.html') # Zeigt das Kurs-anlegen-Formular an, wenn GET oder ungültige POST-Anfrage

@app.route('/logout', methods=['POST']) # Definiert die Route '/logout' für POST-Anfragen
def logout():
    session.clear() # Löscht alle Session-Daten (ausloggen)
    return redirect(url_for('login')) # Weiterleitung zur Login-Seite

@app.route('/verfuegbare_plaetze')
def verfuegbare_plaetze():
    kurs_titel = request.args.get('kurs')  # Kurstitel aus der URL holen
    tag = request.args.get('tag')  # Tag (Datum) aus der URL holen
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)  # Datenbank-Cursor erstellen
    cursor.execute('SELECT id, max_teilnehmer FROM kurse WHERE titel = %s', (kurs_titel,))  # Kursdaten abfragen
    kurs = cursor.fetchone()  # Kursdaten holen
    if not kurs:
        return {'verfuegbar': 0}  # Wenn kein Kurs gefunden, 0 zurückgeben
    kurs_id = kurs['id']  # Kurs-ID speichern
    max_teilnehmer = kurs['max_teilnehmer']  # Maximale Teilnehmerzahl speichern
    gesamt_slots = max_teilnehmer * 9  # 9 Slots pro Tag
    cursor.execute('SELECT COUNT(*) as cnt FROM buchungen WHERE kurs_id = %s AND datum = %s', (kurs_id, tag))
    gebucht = cursor.fetchone()['cnt']
    verfuegbar = gesamt_slots - gebucht  # Verfügbare Plätze berechnen
    if verfuegbar < 0:
        verfuegbar = 0
    return {'verfuegbar': verfuegbar}  # Ergebnis als JSON zurückgeben

if __name__ == '__main__': # Startet die App nur, wenn das Skript direkt ausgeführt wird
    app.run(debug=True) # Startet den Flask-Server im Debug-Modus