# OpenArm Mini Basisprüfbericht · OAML2026102301

| Punkt | Inhalt |
|---|---|
| Dokumentnummer | OAM-L-BENCH-RESULT-OAML2026102301-R01 |
| Berichtssprache | Deutsch |
| Seriennummer / Armseite | OAML2026102301 / Linker Arm L |
| Erstellt am | 2026-10-26T11:07:29+08:00 |
| Ergebnis | PASS |
| Bediener | xlc |
| Projektleiter | pengcheng |
| Prüfstandversion | 0.10.0 |
| Kriterienversion | 2026-10-21.3 |
| LeRobot | 0.6.2 (https://github.com/huggingface/lerobot@eb7a54c6ff49) |
| Hardware-Referenzen | pkooij/open-arms-mini README/BOM; lerobot teleoperators/openarm_mini |
| Stromversorgung | 7,5 V (offizielle Stückliste), Prüfung nach vollständiger Armmontage |

Prüfobjekt: vollständig montierter OpenArm Mini Leader-Arm. Die Motor-IDs wurden nach der Montage einzeln zugewiesen; das Motordrehmoment blieb während der Prüfung deaktiviert.

## 1 Freigabeentscheidung

| Stufe | Prüfpunkt | Ergebnis | Erfasst am | Hinweise |
|---|---|---|---|---|
| S1 | Vorbereitungs-Checkliste | PASS | 2026-10-23T11:21:50+08:00 |  |
| S2 | J8 · Greifer ID schreiben | PASS | 2026-10-23T10:34:37+08:00 |  |
| S2 | J8 · Greifer Neuscan nach Aus/Ein | PASS | 2026-10-23T10:34:46+08:00 |  |
| S2 | J8 · Greifer durch Gelenkbewegung bestätigt | PASS | 2026-10-23T10:35:08+08:00 | Weg 2088 Zählschritte |
| S2 | J7 · Handgelenkdrehung ID schreiben | PASS | 2026-10-23T10:36:16+08:00 |  |
| S2 | J7 · Handgelenkdrehung Neuscan nach Aus/Ein | PASS | 2026-10-23T10:36:23+08:00 |  |
| S2 | J7 · Handgelenkdrehung durch Gelenkbewegung bestätigt | PASS | 2026-10-23T10:36:32+08:00 | Weg 2017 Zählschritte |
| S2 | J6 · Handgelenkbeugung ID schreiben | PASS | 2026-10-23T10:37:16+08:00 |  |
| S2 | J6 · Handgelenkbeugung Neuscan nach Aus/Ein | PASS | 2026-10-23T10:37:26+08:00 |  |
| S2 | J6 · Handgelenkbeugung durch Gelenkbewegung bestätigt | PASS | 2026-10-23T10:37:35+08:00 | Weg 1855 Zählschritte |
| S2 | J5 · Unterarmdrehung ID schreiben | PASS | 2026-10-23T10:38:10+08:00 |  |
| S2 | J5 · Unterarmdrehung Neuscan nach Aus/Ein | PASS | 2026-10-23T10:38:18+08:00 |  |
| S2 | J5 · Unterarmdrehung durch Gelenkbewegung bestätigt | PASS | 2026-10-23T10:38:27+08:00 | Weg 2046 Zählschritte |
| S2 | J4 · Ellbogenbeugung ID schreiben | PASS | 2026-10-23T10:38:46+08:00 |  |
| S2 | J4 · Ellbogenbeugung Neuscan nach Aus/Ein | PASS | 2026-10-23T10:38:53+08:00 |  |
| S2 | J4 · Ellbogenbeugung durch Gelenkbewegung bestätigt | PASS | 2026-10-23T10:39:13+08:00 | Weg 2017 Zählschritte |
| S2 | J3 · Schulterrollung ID schreiben | PASS | 2026-10-23T10:39:30+08:00 |  |
| S2 | J3 · Schulterrollung Neuscan nach Aus/Ein | PASS | 2026-10-23T10:39:36+08:00 |  |
| S2 | J3 · Schulterrollung durch Gelenkbewegung bestätigt | PASS | 2026-10-23T10:39:45+08:00 | Weg 2887 Zählschritte |
| S2 | J2 · Schulterhub ID schreiben | PASS | 2026-10-23T10:39:58+08:00 |  |
| S2 | J2 · Schulterhub Neuscan nach Aus/Ein | PASS | 2026-10-23T10:40:05+08:00 |  |
| S2 | J2 · Schulterhub durch Gelenkbewegung bestätigt | PASS | 2026-10-23T10:40:13+08:00 | Weg 2220 Zählschritte |
| S2 | J1 · Schulterdrehung ID schreiben | PASS | 2026-10-23T10:40:31+08:00 |  |
| S2 | J1 · Schulterdrehung Neuscan nach Aus/Ein | PASS | 2026-10-23T10:40:33+08:00 |  |
| S2 | J1 · Schulterdrehung durch Gelenkbewegung bestätigt | PASS | 2026-10-23T10:40:48+08:00 | Weg 1577 Zählschritte |
| S3 | Elektrische Prüfung aller acht Achsen | PASS | 2026-10-23T10:51:40+08:00 | 8/8 bestanden |
| S3 | Kommunikationsstabilität | PASS | 2026-10-23T11:23:13+08:00 | 11631 Kommunikationsabfragezyklen, 0 Fehler |
| S4 | J1 · Schulterdrehung Gelenkidentität | PASS | 2026-10-23T10:54:22+08:00 |  |
| S4 | J2 · Schulterhub Gelenkidentität | PASS | 2026-10-23T11:12:01+08:00 |  |
| S4 | J3 · Schulterrollung Gelenkidentität | PASS | 2026-10-23T11:12:13+08:00 |  |
| S4 | J4 · Ellbogenbeugung Gelenkidentität | PASS | 2026-10-23T11:12:37+08:00 |  |
| S4 | J5 · Unterarmdrehung Gelenkidentität | PASS | 2026-10-23T11:12:49+08:00 |  |
| S4 | J6 · Handgelenkbeugung Gelenkidentität | PASS | 2026-10-23T11:13:01+08:00 |  |
| S4 | J7 · Handgelenkdrehung Gelenkidentität | PASS | 2026-10-23T11:13:18+08:00 |  |
| S4 | J8 · Greifer Gelenkidentität | PASS | 2026-10-23T11:13:32+08:00 |  |
| S5 | Kalibriervorprüfung | PASS | 2026-10-23T15:24:44+08:00 |  |
| S5 | Offizielle Kalibrierung gespeichert | PASS | 2026-10-23T15:25:57+08:00 |  |
| S5 | Konsistenzprüfung | PASS | 2026-10-23T15:26:03+08:00 |  |
| S5 | Konsistenzprüfung nach Aus/Ein | PASS | 2026-10-23T15:26:42+08:00 |  |
| S6 | Offizielles Auslesen: Nullstellung | PASS | 2026-10-23T15:26:49+08:00 |  |
| S6 | Offizielles Auslesen: Greifer offen | PASS | 2026-10-23T15:29:13+08:00 |  |
| S6 | Offizielles Auslesen: J6 · Handgelenkbeugung schwenken | PASS | 2026-10-23T15:29:54+08:00 |  |
| S6 | Offizielles Auslesen: J7 · Handgelenkdrehung schwenken | PASS | 2026-10-23T15:30:26+08:00 |  |

## 2 S1 Vorbereitung

| Checklistenpunkt | Ergebnis |
|---|---|
| Netzteil 7,50 V / ≥2 A (offizielle Stückliste), rot plus, schwarz minus, OCP aus, OUTPUT an | ✔ |
| Der Arm ist vollständig montiert und hängt frei an einer senkrechten Säule (wie auf dem offiziellen Foto) | ✔ |
| Waveshare-Treiberplatine an der 7,5-V-Versorgung und per USB an diesem Rechner | ✔ |
| Jumper der Waveshare-Treiberplatine auf B | ✔ |
| Greiferteile (J8 L/R, Abzug L/R, J8-Halter L/R) passen zur Armseite in der Seriennummer | ✔ |
| Erfasst am | 2026-10-23T11:21:50+08:00 |

## 3 S2 IDs nach der Montage einzeln schreiben

Die Motor-IDs wurden nach der Montage einzeln zugewiesen und durch Neuscan nach Aus/Ein sowie Gelenkpositionsrückmeldung geprüft.

| Gelenk | Ursprüngliche ID | Geschriebene ID | Neuscan nach Aus/Ein | Bestätigungsweg | Spannung V | Firmware | Bestätigung |
|---|---|---|---|---|---|---|---|
| J8 · Greifer | 1 | 8 | Ja | 2088 | 7.3 | 3.10 | Bestanden |
| J7 · Handgelenkdrehung | 1 | 7 | Ja | 2017 | 7.3 | 3.10 | Bestanden |
| J6 · Handgelenkbeugung | 1 | 6 | Ja | 1855 | 7.3 | 3.10 | Bestanden |
| J5 · Unterarmdrehung | 1 | 5 | Ja | 2046 | 7.4 | 3.10 | Bestanden |
| J4 · Ellbogenbeugung | 1 | 4 | Ja | 2017 | 7.3 | 3.10 | Bestanden |
| J3 · Schulterrollung | 1 | 3 | Ja | 2887 | 7.2 | 3.10 | Bestanden |
| J2 · Schulterhub | 1 | 2 | Ja | 2220 | 7.3 | 3.10 | Bestanden |
| J1 · Schulterdrehung | 1 | 1 | Ja | 1577 | 7.4 | 3.10 | Bestanden |

## 4 S3 Elektrik- und Kommunikationsprüfung des Gesamtarms

| Gelenk | ID | Position | Spannung V | Temperatur °C | Status | Drehmoment | Firmware | Überspannungsgrenze V | Übertemperaturgrenze °C | Phase | Max_Acc | Bewertung |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| J1 · Schulterdrehung | 1 | 831 | 7.3 | 28 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |
| J2 · Schulterhub | 2 | 2881 | 7.3 | 27 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |
| J3 · Schulterrollung | 3 | 2298 | 7.3 | 28 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |
| J4 · Ellbogenbeugung | 4 | 761 | 7.2 | 29 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |
| J5 · Unterarmdrehung | 5 | 2673 | 7.3 | 28 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |
| J6 · Handgelenkbeugung | 6 | 1257 | 7.2 | 28 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |
| J7 · Handgelenkdrehung | 7 | 2120 | 7.3 | 29 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |
| J8 · Greifer | 8 | 2777 | 7.2 | 28 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |

Versorgungsprofil mini_field_7v5; Firmware 3.10; Spannungsstreuung 0.1 V (nur erfasst). Erfasst am 2026-10-23T10:51:40+08:00.

Kommunikationsstabilität: 60 s kontinuierliche Abfrage; 11631 Kommunikationsabfragezyklen, 93048 Motorregister-Lesevorgänge, 0 Fehler. Abfragezyklen sind keine mechanischen Bewegungen oder separaten Prüfungen.

## 5 S4 Gelenkidentität und Beweglichkeit

| Geprüftes Gelenk | Weg (Zählschritte) | Motor mit größtem Weg | Zweitgrößter Weg | Bewertung |
|---|---|---|---|---|
| J1 · Schulterdrehung | 972 | J1 · Schulterdrehung | 134 | Bestanden |
| J2 · Schulterhub | 1811 | J2 · Schulterhub | 86 | Bestanden |
| J3 · Schulterrollung | 3151 | J3 · Schulterrollung | 106 | Bestanden |
| J4 · Ellbogenbeugung | 1732 | J4 · Ellbogenbeugung | 108 | Bestanden |
| J5 · Unterarmdrehung | 2572 | J5 · Unterarmdrehung | 280 | Bestanden |
| J6 · Handgelenkbeugung | 904 | J6 · Handgelenkbeugung | 249 | Bestanden |
| J7 · Handgelenkdrehung | 2023 | J7 · Handgelenkdrehung | 120 | Bestanden |
| J8 · Greifer | 2414 | J8 · Greifer | 51 | Bestanden |

Kriterium: Der Motor mit dem größten Weg muss das geprüfte Gelenk sein und ≥ zweitgrößter Weg × 3; geprüfter Weg ≥ 100 Zählschritte.

## 6 S5 Offizielle Kalibrierung und Konsistenzprüfung

| Gelenk | id | drive_mode | homing_offset | range_min | range_max |
|---|---|---|---|---|---|
| J1 · Schulterdrehung | 1 | 0 | -1206 | 0 | 4095 |
| J2 · Schulterhub | 2 | 0 | 838 | 0 | 4095 |
| J3 · Schulterrollung | 3 | 0 | -760 | 0 | 4095 |
| J4 · Ellbogenbeugung | 4 | 0 | -1254 | 0 | 4095 |
| J5 · Unterarmdrehung | 5 | 0 | 1279 | 0 | 4095 |
| J6 · Handgelenkbeugung | 6 | 0 | -717 | 0 | 4095 |
| J7 · Handgelenkdrehung | 7 | 0 | -34 | 0 | 4095 |
| J8 · Greifer | 8 | 0 | 1637 | 2047 | 3732 |

Kalibrierung gespeichert am 2026-10-23T15:25:57+08:00.

## 7 S6 Ausleseprüfung mit offiziellem Treiber

| Zeit | Modus | Gelenk | Messwerte | Bewertung |
|---|---|---|---|---|
| 2026-10-23T15:26:49+08:00 | Nullstellung |  | S6.calibrated=True; S6.zero_pose=2.86; S6.gripper_closed=0 | Bestanden |
| 2026-10-23T15:29:13+08:00 | Greifer offen |  | S6.calibrated=True; S6.gripper_open=-65 | Bestanden |
| 2026-10-23T15:29:54+08:00 | Schwenken | J6 · Handgelenkbeugung | S6.calibrated=True; S6.remap=145.93; S6.direction=+ | Bestanden |
| 2026-10-23T15:30:26+08:00 | Schwenken | J7 · Handgelenkdrehung | S6.calibrated=True; S6.remap=177.23; S6.direction=- | Bestanden |

Teleoperationsbefehl für den Kunden: Nicht unverändert kopieren und ausführen. Zuerst die LeRobot-Umgebung aktivieren, `<can0>` durch die CAN-Schnittstelle des Followers und `<follower_id>` durch dessen Kennung ersetzen sowie prüfen, ob `--teleop.port` dem Mini-Seriellport am Kundenrechner entspricht. Danach kann der Befehl kopiert und ausgeführt werden.

```
lerobot-teleoperate \
    --robot.type=openarm_follower --robot.port=<can0> --robot.side=left --robot.id=<follower_id> \
    --teleop.type=openarm_mini --teleop.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5959112505-if00 \
    --teleop.side=left --teleop.id=OAML2026102301
```

## 8 Freigabekriterien

| Kennung | Beschreibung | Grenzwert | Grundlage |
|---|---|---|---|
| S1.checklist | Vorbereitungs-Checkliste vollständig bestätigt, Bediener erfasst | all | Offiziell |
| S2.single_on_bus | Broadcast-Ping von genau einem Motor beantwortet, Modell 777 | 1 | Offiziell |
| S2.voltage | Gemessene Spannung innerhalb der Toleranz von 7,5 V und unter Nennwert + Toleranz | 1 V | Abgeleitet |
| S2.persisted | Nach ≥5 s stromlos unter neuer ID und 1 Mbit/s wiedergefunden | rescan | Abgeleitet |
| S2.joint_confirmed | Nur dieses Gelenk bewegt: Wertänderung ≥ Schwelle (die ID liegt am Motor dieses Gelenks) | 100 counts | Abgeleitet |
| S3.present | IDs 1–8 antworten alle, Modell 777 | 8 | Offiziell |
| S3.firmware_same | Gleiche Firmware auf allen 8 (von LeRobot beim Verbinden geprüft) | same | Offiziell |
| S3.voltage | Jede Spannung innerhalb der Toleranz von 7,5 V | 1 V | Abgeleitet |
| S3.temperature | Temperatur im Ruhezustand ohne Drehmoment ≤ Schwelle | 40 °C | Abgeleitet |
| S3.status | Statusregister ist 0 (keine Alarmbits) | 0 | Abgeleitet |
| S3.torque_off | Drehmoment deaktiviert | 0 | Abgeleitet |
| S3.comm | Fortlaufendes Lesen aller 8 Positionen, 0 Fehler | 60 s | Abgeleitet |
| S4.identity | Bei Bewegung eines Gelenks ist sein Weg am größten und ≥ zweitgrößter × Schwelle | 3 | Abgeleitet |
| S4.span | Weg des geprüften Gelenks ≥ Schwelle | 100 counts | Abgeleitet |
| S5.precheck | Vorprüfung: Werte innerhalb einer Umdrehung, erwarteter Offset \|·\| ≤ 2047 | 2047 | Offiziell |
| S5.saved | Offizielle Kalibrierung hat die Speichermarke ausgegeben | saved | Offiziell |
| S5.consistent | Kalibrierdatei und EEPROM 8/8 konsistent, Phase=12 | 8 | Offiziell |
| S5.consistent_power_cycled | Nach ≥5 s stromlos erneut 8/8 konsistent | 8 | Abgeleitet |
| S6.calibrated | Offizieller Treiber meldet kalibriert (is_calibrated) | is_calibrated | Offiziell |
| S6.zero_pose | In Nullstellung J1–J7 Werte \|·\| ≤ Schwelle | 15 ° | Abgeleitet |
| S6.gripper_closed | Greifer geschlossen ≥ Schwelle (nahe 0°) | -10 ° | Offiziell |
| S6.gripper_open | Greifer offen ≤ Schwelle (nahe −65°) | -50 ° | Offiziell |
| S6.remap | Beim Schwenken von J6/J7 ändert sich der getauschte Schlüssel am stärksten | joint_6<->joint_7 | Offiziell |

## 9 Lieferhinweis

Dieser Bericht deckt die Werksprüfungen S1–S7 ab. Follower-Kopplung und weitere projektspezifische Prüfungen erfolgen bei Bedarf separat.

## 10 Freigabeunterschriften

| Rolle | Name | Unterschrift | Datum |
|---|---|---|---|
| Prüfer | xlc |  |  |
| Projektleiter | pengcheng |  |  |
| Prüfer (Vier-Augen-Prinzip) |  |  |  |
