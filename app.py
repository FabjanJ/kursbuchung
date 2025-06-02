from flask import Flask, render_template, request, redirect, session, url_for
from datetime import datetime, timedelta
from flask_mysqldb import MySQL
import MySQLdb.cursors
import config

app = Flask(__name__)
app.secret_key = 'secret_key'

# DB Config laden
app.config.from_object(config)

mysql = MySQL(app)

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pw = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM benutzer WHERE benutzername = %s', (user,))
        account = cursor.fetchone()
        if account and account['passwort'] == pw:  # nur testweise – kein Hash
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['benutzername']
            if user == 'adminuser' and pw == 'adminuser123':
                return redirect(url_for('kurs_anlegen'))
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form['username']
        pw = request.form['password']
        cursor = mysql.connection.cursor()
        cursor.execute('INSERT INTO benutzer (benutzername, passwort) VALUES (%s, %s)', (user, pw))
        mysql.connection.commit()
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    delta = int(request.args.get('woche', 0))
    heute = datetime.today()
    start_montag = heute - timedelta(days=heute.weekday()) + timedelta(weeks=delta)
    end_sonntag = start_montag + timedelta(days=6)

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # Alle Kurstitel für Dropdown, aber nur Kurse im aktuellen Wochenbereich
    cursor.execute('SELECT DISTINCT titel FROM kurse')
    kurstitel = [row['titel'] for row in cursor.fetchall()]

    # Gewählten Kurstitel aus Query oder Standard, aber nur wenn es Kurse gibt
    if kurstitel:
        gewaehlter_kurs = request.args.get('kurs') or kurstitel[0]
    else:
        gewaehlter_kurs = None

    # Kursobjekt für gewählten Titel und Zeitraum nur suchen, wenn gewaehlter_kurs existiert
    kurs = None
    if gewaehlter_kurs:
        cursor.execute('SELECT * FROM kurse WHERE titel = %s', (gewaehlter_kurs,))
        kurs = cursor.fetchone()
        # Kurs nur anzeigen, wenn der aktuelle Wochenbereich mit von_datum/bis_datum schneidet
        kurs_id = None
        if kurs and kurs['von_datum'] and kurs['bis_datum']:
            import datetime as dt
            von = kurs['von_datum']
            bis = kurs['bis_datum']
            if isinstance(von, str):
                von = dt.datetime.strptime(von, '%Y-%m-%d').date()
            if isinstance(bis, str):
                bis = dt.datetime.strptime(bis, '%Y-%m-%d').date()
            if von <= end_sonntag.date() and bis >= start_montag.date():
                kurs_id = kurs['id']
        else:
            kurs = None
    else:
        kurs_id = None

    # Alle Buchungen der Woche für den gewählten Kurs
    if kurs_id:
        # Hole max_teilnehmer für den Kurs
        cursor.execute('SELECT max_teilnehmer FROM kurse WHERE id = %s', (kurs_id,))
        kurs_info = cursor.fetchone()
        max_teilnehmer = kurs_info['max_teilnehmer'] if kurs_info and kurs_info['max_teilnehmer'] is not None else None
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
        max_teilnehmer = None

    return render_template('dashboard.html', start=start_montag.date(), delta=delta, timedelta=timedelta, 
                           kurstitel=kurstitel, gewaehlter_kurs=gewaehlter_kurs, buchungen=buchungen, eigene_buchungen=eigene_buchungen, kurs=kurs, max_teilnehmer=max_teilnehmer)

@app.route('/buchen', methods=['POST'])
def buchen():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    slots = request.json.get('slots', [])
    kurs_titel = request.json.get('kurs')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # Kurs-ID für Titel finden
    cursor.execute('SELECT id FROM kurse WHERE titel = %s', (kurs_titel,))
    kurs = cursor.fetchone()
    if not kurs:
        return {'status': 'error', 'msg': 'Kurs nicht gefunden'}
    kurs_id = kurs['id']
    for slot in slots:
        datum = slot['datum']
        stunde = slot['stunde']
        # Prüfen ob schon gebucht
        cursor.execute('SELECT * FROM buchungen WHERE kurs_id = %s AND benutzer_id = %s AND datum = %s AND stunde = %s', (kurs_id, session['id'], datum, stunde))
        if not cursor.fetchone():
            cursor.execute('INSERT INTO buchungen (kurs_id, benutzer_id, datum, stunde) VALUES (%s, %s, %s, %s)', (kurs_id, session['id'], datum, stunde))
    mysql.connection.commit()
    return {'status': 'ok'}

@app.route('/kurs_anlegen', methods=['GET', 'POST'])
def kurs_anlegen():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        titel = request.form['titel']
        beschreibung = request.form['beschreibung']
        von_datum = request.form['von_datum']
        bis_datum = request.form['bis_datum']
        cursor = mysql.connection.cursor()
        cursor.execute('INSERT INTO kurse (titel, beschreibung, von_datum, bis_datum) VALUES (%s, %s, %s, %s)', (titel, beschreibung, von_datum, bis_datum))
        mysql.connection.commit()
        return redirect(url_for('dashboard'))
    return render_template('kurs_anlegen.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)