CREATE DATABASE IF NOT EXISTS buchungssystem;
USE buchungssystem;

CREATE TABLE IF NOT EXISTS benutzer (
    id INT AUTO_INCREMENT PRIMARY KEY,
    benutzername VARCHAR(50) UNIQUE,
    passwort VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS kurse (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titel VARCHAR(100),
    beschreibung TEXT,
    max_teilnehmer INT;
    von_datum DATE,
    bis_datum DATE
);

CREATE TABLE IF NOT EXISTS buchungen (
    id INT AUTO_INCREMENT PRIMARY KEY,
    kurs_id INT,
    benutzer_id INT,
    datum DATE,
    stunde INT,
    UNIQUE(kurs_id, benutzer_id, datum, stunde),
    FOREIGN KEY (kurs_id) REFERENCES kurse(id),
    FOREIGN KEY (benutzer_id) REFERENCES benutzer(id)
);
