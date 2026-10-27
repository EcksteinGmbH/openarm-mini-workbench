# OpenArm Mini Basisprüfbericht · OAMR2026102302

| Punkt | Inhalt |
|---|---|
| Dokumentnummer | OAM-R-BENCH-RESULT-OAMR2026102302-R01 |
| Berichtssprache | Deutsch |
| Seriennummer / Armseite | OAMR2026102302 / Rechter Arm R |
| Erstellt am | 2026-10-26T11:07:44+08:00 |
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
| S1 | Vorbereitungs-Checkliste | PASS | 2026-10-23T16:11:04+08:00 |  |
| S2 | J8 · Greifer ID schreiben | PASS | 2026-10-23T16:11:50+08:00 |  |
| S2 | J8 · Greifer Neuscan nach Aus/Ein | PASS | 2026-10-23T16:11:55+08:00 |  |
| S2 | J8 · Greifer durch Gelenkbewegung bestätigt | PASS | 2026-10-23T16:12:04+08:00 | Weg 1719 Zählschritte |
| S2 | J7 · Handgelenkdrehung ID schreiben | PASS | 2026-10-23T16:12:38+08:00 |  |
| S2 | J7 · Handgelenkdrehung Neuscan nach Aus/Ein | PASS | 2026-10-23T16:12:44+08:00 |  |
| S2 | J7 · Handgelenkdrehung durch Gelenkbewegung bestätigt | PASS | 2026-10-23T16:12:54+08:00 | Weg 913 Zählschritte |
| S2 | J6 · Handgelenkbeugung ID schreiben | PASS | 2026-10-23T16:13:20+08:00 |  |
| S2 | J6 · Handgelenkbeugung Neuscan nach Aus/Ein | PASS | 2026-10-23T16:13:27+08:00 |  |
| S2 | J6 · Handgelenkbeugung durch Gelenkbewegung bestätigt | PASS | 2026-10-23T16:13:36+08:00 | Weg 1232 Zählschritte |
| S2 | J5 · Unterarmdrehung ID schreiben | PASS | 2026-10-23T16:13:49+08:00 |  |
| S2 | J5 · Unterarmdrehung Neuscan nach Aus/Ein | PASS | 2026-10-23T16:13:53+08:00 |  |
| S2 | J5 · Unterarmdrehung durch Gelenkbewegung bestätigt | PASS | 2026-10-23T16:14:04+08:00 | Weg 821 Zählschritte |
| S2 | J4 · Ellbogenbeugung ID schreiben | PASS | 2026-10-23T16:14:33+08:00 |  |
| S2 | J4 · Ellbogenbeugung Neuscan nach Aus/Ein | PASS | 2026-10-23T16:14:39+08:00 |  |
| S2 | J4 · Ellbogenbeugung durch Gelenkbewegung bestätigt | PASS | 2026-10-23T16:14:48+08:00 | Weg 874 Zählschritte |
| S2 | J3 · Schulterrollung ID schreiben | PASS | 2026-10-23T16:15:03+08:00 |  |
| S2 | J3 · Schulterrollung Neuscan nach Aus/Ein | PASS | 2026-10-23T16:15:08+08:00 |  |
| S2 | J3 · Schulterrollung durch Gelenkbewegung bestätigt | PASS | 2026-10-23T16:15:17+08:00 | Weg 935 Zählschritte |
| S2 | J2 · Schulterhub ID schreiben | PASS | 2026-10-23T16:15:45+08:00 |  |
| S2 | J2 · Schulterhub Neuscan nach Aus/Ein | PASS | 2026-10-23T16:15:49+08:00 |  |
| S2 | J2 · Schulterhub durch Gelenkbewegung bestätigt | PASS | 2026-10-23T16:15:58+08:00 | Weg 636 Zählschritte |
| S2 | J1 · Schulterdrehung ID schreiben | PASS | 2026-10-23T16:16:10+08:00 |  |
| S2 | J1 · Schulterdrehung Neuscan nach Aus/Ein | PASS | 2026-10-23T16:16:16+08:00 |  |
| S2 | J1 · Schulterdrehung durch Gelenkbewegung bestätigt | PASS | 2026-10-23T16:16:25+08:00 | Weg 478 Zählschritte |
| S3 | Elektrische Prüfung aller acht Achsen | PASS | 2026-10-23T16:20:16+08:00 | 8/8 bestanden |
| S3 | Kommunikationsstabilität | PASS | 2026-10-23T16:21:17+08:00 | 11501 Kommunikationsabfragezyklen, 0 Fehler |
| S4 | J1 · Schulterdrehung Gelenkidentität | PASS | 2026-10-23T16:21:41+08:00 |  |
| S4 | J2 · Schulterhub Gelenkidentität | PASS | 2026-10-23T16:21:51+08:00 |  |
| S4 | J3 · Schulterrollung Gelenkidentität | PASS | 2026-10-23T16:22:00+08:00 |  |
| S4 | J4 · Ellbogenbeugung Gelenkidentität | PASS | 2026-10-23T16:22:21+08:00 |  |
| S4 | J5 · Unterarmdrehung Gelenkidentität | PASS | 2026-10-23T16:22:30+08:00 |  |
| S4 | J6 · Handgelenkbeugung Gelenkidentität | PASS | 2026-10-23T16:22:52+08:00 |  |
| S4 | J7 · Handgelenkdrehung Gelenkidentität | PASS | 2026-10-23T16:23:01+08:00 |  |
| S4 | J8 · Greifer Gelenkidentität | PASS | 2026-10-23T16:23:11+08:00 |  |
| S5 | Kalibriervorprüfung | PASS | 2026-10-23T16:23:14+08:00 |  |
| S5 | Offizielle Kalibrierung gespeichert | PASS | 2026-10-23T16:23:43+08:00 |  |
| S5 | Konsistenzprüfung | PASS | 2026-10-23T16:23:56+08:00 |  |
| S5 | Konsistenzprüfung nach Aus/Ein | PASS | 2026-10-23T16:24:06+08:00 |  |
| S6 | Offizielles Auslesen: Nullstellung | PASS | 2026-10-23T16:24:26+08:00 |  |
| S6 | Offizielles Auslesen: Greifer offen | PASS | 2026-10-23T16:24:36+08:00 |  |
| S6 | Offizielles Auslesen: J6 · Handgelenkbeugung schwenken | PASS | 2026-10-23T16:24:50+08:00 |  |
| S6 | Offizielles Auslesen: J7 · Handgelenkdrehung schwenken | PASS | 2026-10-23T16:25:03+08:00 |  |

## 2 S1 Vorbereitung

| Checklistenpunkt | Ergebnis |
|---|---|
| Netzteil 7,50 V / ≥2 A (offizielle Stückliste), rot plus, schwarz minus, OCP aus, OUTPUT an | ✔ |
| Der Arm ist vollständig montiert und hängt frei an einer senkrechten Säule (wie auf dem offiziellen Foto) | ✔ |
| Waveshare-Treiberplatine an der 7,5-V-Versorgung und per USB an diesem Rechner | ✔ |
| Jumper der Waveshare-Treiberplatine auf B | ✔ |
| Greiferteile (J8 L/R, Abzug L/R, J8-Halter L/R) passen zur Armseite in der Seriennummer | ✔ |
| Erfasst am | 2026-10-23T16:11:04+08:00 |

## 3 S2 IDs nach der Montage einzeln schreiben

Die Motor-IDs wurden nach der Montage einzeln zugewiesen und durch Neuscan nach Aus/Ein sowie Gelenkpositionsrückmeldung geprüft.

| Gelenk | Ursprüngliche ID | Geschriebene ID | Neuscan nach Aus/Ein | Bestätigungsweg | Spannung V | Firmware | Bestätigung |
|---|---|---|---|---|---|---|---|
| J8 · Greifer | 1 | 8 | Ja | 1719 | 7.3 | 3.10 | Bestanden |
| J7 · Handgelenkdrehung | 1 | 7 | Ja | 913 | 7.3 | 3.10 | Bestanden |
| J6 · Handgelenkbeugung | 1 | 6 | Ja | 1232 | 7.3 | 3.10 | Bestanden |
| J5 · Unterarmdrehung | 1 | 5 | Ja | 821 | 7.2 | 3.10 | Bestanden |
| J4 · Ellbogenbeugung | 1 | 4 | Ja | 874 | 7.3 | 3.10 | Bestanden |
| J3 · Schulterrollung | 1 | 3 | Ja | 935 | 7.3 | 3.10 | Bestanden |
| J2 · Schulterhub | 1 | 2 | Ja | 636 | 7.2 | 3.10 | Bestanden |
| J1 · Schulterdrehung | 8 | 1 | Ja | 478 | 7.3 | 3.10 | Bestanden |

## 4 S3 Elektrik- und Kommunikationsprüfung des Gesamtarms

| Gelenk | ID | Position | Spannung V | Temperatur °C | Status | Drehmoment | Firmware | Überspannungsgrenze V | Übertemperaturgrenze °C | Phase | Max_Acc | Bewertung |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| J1 · Schulterdrehung | 1 | 1557 | 7.2 | 27 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |
| J2 · Schulterhub | 2 | 3481 | 7.2 | 27 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |
| J3 · Schulterrollung | 3 | 1973 | 7.2 | 27 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |
| J4 · Ellbogenbeugung | 4 | 1570 | 7.3 | 29 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |
| J5 · Unterarmdrehung | 5 | 468 | 7.2 | 28 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |
| J6 · Handgelenkbeugung | 6 | 2904 | 7.2 | 28 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |
| J7 · Handgelenkdrehung | 7 | 1106 | 7.2 | 27 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |
| J8 · Greifer | 8 | 2021 | 7.3 | 27 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Bestanden |

Versorgungsprofil mini_field_7v5; Firmware 3.10; Spannungsstreuung 0.1 V (nur erfasst). Erfasst am 2026-10-23T16:20:16+08:00.

Kommunikationsstabilität: 60 s kontinuierliche Abfrage; 11501 Kommunikationsabfragezyklen, 92008 Motorregister-Lesevorgänge, 0 Fehler. Abfragezyklen sind keine mechanischen Bewegungen oder separaten Prüfungen.

## 5 S4 Gelenkidentität und Beweglichkeit

| Geprüftes Gelenk | Weg (Zählschritte) | Motor mit größtem Weg | Zweitgrößter Weg | Bewertung |
|---|---|---|---|---|
| J1 · Schulterdrehung | 948 | J1 · Schulterdrehung | 136 | Bestanden |
| J2 · Schulterhub | 399 | J2 · Schulterhub | 56 | Bestanden |
| J3 · Schulterrollung | 2276 | J3 · Schulterrollung | 65 | Bestanden |
| J4 · Ellbogenbeugung | 629 | J4 · Ellbogenbeugung | 87 | Bestanden |
| J5 · Unterarmdrehung | 1920 | J5 · Unterarmdrehung | 499 | Bestanden |
| J6 · Handgelenkbeugung | 1142 | J6 · Handgelenkbeugung | 101 | Bestanden |
| J7 · Handgelenkdrehung | 2031 | J7 · Handgelenkdrehung | 37 | Bestanden |
| J8 · Greifer | 2410 | J8 · Greifer | 76 | Bestanden |

Kriterium: Der Motor mit dem größten Weg muss das geprüfte Gelenk sein und ≥ zweitgrößter Weg × 3; geprüfter Weg ≥ 100 Zählschritte.

## 6 S5 Offizielle Kalibrierung und Konsistenzprüfung

| Gelenk | id | drive_mode | homing_offset | range_min | range_max |
|---|---|---|---|---|---|
| J1 · Schulterdrehung | 1 | 0 | -485 | 0 | 4095 |
| J2 · Schulterhub | 2 | 0 | 1430 | 0 | 4095 |
| J3 · Schulterrollung | 3 | 0 | -98 | 0 | 4095 |
| J4 · Ellbogenbeugung | 4 | 0 | -508 | 0 | 4095 |
| J5 · Unterarmdrehung | 5 | 0 | -1551 | 0 | 4095 |
| J6 · Handgelenkbeugung | 6 | 0 | 833 | 0 | 4095 |
| J7 · Handgelenkdrehung | 7 | 0 | -927 | 0 | 4095 |
| J8 · Greifer | 8 | 1 | -26 | 351 | 2047 |

Kalibrierung gespeichert am 2026-10-23T16:23:43+08:00.

## 7 S6 Ausleseprüfung mit offiziellem Treiber

| Zeit | Modus | Gelenk | Messwerte | Bewertung |
|---|---|---|---|---|
| 2026-10-23T16:24:26+08:00 | Nullstellung |  | S6.calibrated=True; S6.zero_pose=1.29; S6.gripper_closed=0 | Bestanden |
| 2026-10-23T16:24:36+08:00 | Greifer offen |  | S6.calibrated=True; S6.gripper_open=-65 | Bestanden |
| 2026-10-23T16:24:50+08:00 | Schwenken | J6 · Handgelenkbeugung | S6.calibrated=True; S6.remap=91.34; S6.direction=- | Bestanden |
| 2026-10-23T16:25:03+08:00 | Schwenken | J7 · Handgelenkdrehung | S6.calibrated=True; S6.remap=128.53; S6.direction=- | Bestanden |

Teleoperationsbefehl für den Kunden: Nicht unverändert kopieren und ausführen. Zuerst die LeRobot-Umgebung aktivieren, `<can0>` durch die CAN-Schnittstelle des Followers und `<follower_id>` durch dessen Kennung ersetzen sowie prüfen, ob `--teleop.port` dem Mini-Seriellport am Kundenrechner entspricht. Danach kann der Befehl kopiert und ausgeführt werden.

```
lerobot-teleoperate \
    --robot.type=openarm_follower --robot.port=<can0> --robot.side=right --robot.id=<follower_id> \
    --teleop.type=openarm_mini --teleop.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5959112505-if00 \
    --teleop.side=right --teleop.id=OAMR2026102302
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
