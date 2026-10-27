# OpenArm Mini Basic Test Report · OAML2026102301

| Item | Content |
|---|---|
| Document ID | OAM-L-BENCH-RESULT-OAML2026102301-R01 |
| Report language | English |
| Serial / arm side | OAML2026102301 / Left arm L |
| Generated at | 2026-10-26T11:07:28+08:00 |
| Verdict | PASS |
| Operator | xlc |
| Project Lead | pengcheng |
| Workstation version | 0.10.0 |
| Criteria version | 2026-10-21.3 |
| LeRobot | 0.6.2 (https://github.com/huggingface/lerobot@eb7a54c6ff49) |
| Hardware references | pkooij/open-arms-mini README/BOM; lerobot teleoperators/openarm_mini |
| Power supply | 7.5 V (official BOM), tested after full-arm assembly |

Test object: fully assembled OpenArm Mini Leader arm. Motor IDs were assigned individually after assembly; motor torque remained disabled throughout testing.

## 1 Release verdict

| Stage | Test item | Result | Recorded at | Notes |
|---|---|---|---|---|
| S1 | Preparation checklist | PASS | 2026-10-23T11:21:50+08:00 |  |
| S2 | J8 · Gripper write ID | PASS | 2026-10-23T10:34:37+08:00 |  |
| S2 | J8 · Gripper rescan after power cycle | PASS | 2026-10-23T10:34:46+08:00 |  |
| S2 | J8 · Gripper confirmed by moving the joint | PASS | 2026-10-23T10:35:08+08:00 | span 2088 counts |
| S2 | J7 · Wrist Roll write ID | PASS | 2026-10-23T10:36:16+08:00 |  |
| S2 | J7 · Wrist Roll rescan after power cycle | PASS | 2026-10-23T10:36:23+08:00 |  |
| S2 | J7 · Wrist Roll confirmed by moving the joint | PASS | 2026-10-23T10:36:32+08:00 | span 2017 counts |
| S2 | J6 · Wrist Flex write ID | PASS | 2026-10-23T10:37:16+08:00 |  |
| S2 | J6 · Wrist Flex rescan after power cycle | PASS | 2026-10-23T10:37:26+08:00 |  |
| S2 | J6 · Wrist Flex confirmed by moving the joint | PASS | 2026-10-23T10:37:35+08:00 | span 1855 counts |
| S2 | J5 · Forearm Rotation write ID | PASS | 2026-10-23T10:38:10+08:00 |  |
| S2 | J5 · Forearm Rotation rescan after power cycle | PASS | 2026-10-23T10:38:18+08:00 |  |
| S2 | J5 · Forearm Rotation confirmed by moving the joint | PASS | 2026-10-23T10:38:27+08:00 | span 2046 counts |
| S2 | J4 · Elbow Flex write ID | PASS | 2026-10-23T10:38:46+08:00 |  |
| S2 | J4 · Elbow Flex rescan after power cycle | PASS | 2026-10-23T10:38:53+08:00 |  |
| S2 | J4 · Elbow Flex confirmed by moving the joint | PASS | 2026-10-23T10:39:13+08:00 | span 2017 counts |
| S2 | J3 · Shoulder Roll write ID | PASS | 2026-10-23T10:39:30+08:00 |  |
| S2 | J3 · Shoulder Roll rescan after power cycle | PASS | 2026-10-23T10:39:36+08:00 |  |
| S2 | J3 · Shoulder Roll confirmed by moving the joint | PASS | 2026-10-23T10:39:45+08:00 | span 2887 counts |
| S2 | J2 · Shoulder Lift write ID | PASS | 2026-10-23T10:39:58+08:00 |  |
| S2 | J2 · Shoulder Lift rescan after power cycle | PASS | 2026-10-23T10:40:05+08:00 |  |
| S2 | J2 · Shoulder Lift confirmed by moving the joint | PASS | 2026-10-23T10:40:13+08:00 | span 2220 counts |
| S2 | J1 · Shoulder Pan write ID | PASS | 2026-10-23T10:40:31+08:00 |  |
| S2 | J1 · Shoulder Pan rescan after power cycle | PASS | 2026-10-23T10:40:33+08:00 |  |
| S2 | J1 · Shoulder Pan confirmed by moving the joint | PASS | 2026-10-23T10:40:48+08:00 | span 1577 counts |
| S3 | Eight-axis electrical check | PASS | 2026-10-23T10:51:40+08:00 | 8/8 passed |
| S3 | Communication stability | PASS | 2026-10-23T11:23:13+08:00 | 11631 communication polling cycles, 0 failures |
| S4 | J1 · Shoulder Pan joint identity | PASS | 2026-10-23T10:54:22+08:00 |  |
| S4 | J2 · Shoulder Lift joint identity | PASS | 2026-10-23T11:12:01+08:00 |  |
| S4 | J3 · Shoulder Roll joint identity | PASS | 2026-10-23T11:12:13+08:00 |  |
| S4 | J4 · Elbow Flex joint identity | PASS | 2026-10-23T11:12:37+08:00 |  |
| S4 | J5 · Forearm Rotation joint identity | PASS | 2026-10-23T11:12:49+08:00 |  |
| S4 | J6 · Wrist Flex joint identity | PASS | 2026-10-23T11:13:01+08:00 |  |
| S4 | J7 · Wrist Roll joint identity | PASS | 2026-10-23T11:13:18+08:00 |  |
| S4 | J8 · Gripper joint identity | PASS | 2026-10-23T11:13:32+08:00 |  |
| S5 | Calibration precheck | PASS | 2026-10-23T15:24:44+08:00 |  |
| S5 | Official calibration saved | PASS | 2026-10-23T15:25:57+08:00 |  |
| S5 | Consistency check | PASS | 2026-10-23T15:26:03+08:00 |  |
| S5 | Consistency check after power cycle | PASS | 2026-10-23T15:26:42+08:00 |  |
| S6 | Official readout: zero pose | PASS | 2026-10-23T15:26:49+08:00 |  |
| S6 | Official readout: gripper open | PASS | 2026-10-23T15:29:13+08:00 |  |
| S6 | Official readout: J6 · Wrist Flex sweep | PASS | 2026-10-23T15:29:54+08:00 |  |
| S6 | Official readout: J7 · Wrist Roll sweep | PASS | 2026-10-23T15:30:26+08:00 |  |

## 2 S1 Preparation

| Checklist item | Result |
|---|---|
| Supply 7.50 V / ≥2 A (official BOM), red positive, black negative, OCP off, OUTPUT on | ✔ |
| The arm is fully assembled and mounted on a vertical post so it hangs freely (as in the official photo) | ✔ |
| Waveshare driver board connected to the 7.5 V supply and by USB to this computer | ✔ |
| Waveshare driver board jumper set to B | ✔ |
| Gripper parts (J8 L/R, trigger L/R, J8 holder L/R) match the arm side in the serial | ✔ |
| Recorded at | 2026-10-23T11:21:50+08:00 |

## 3 S2 Write each ID after assembly

Motor IDs were assigned individually after assembly and verified by a power-cycle rescan and joint-position feedback.

| Joint | Original ID | Written ID | Power-cycle rescan | Confirmation span | Voltage V | Firmware | Confirmation |
|---|---|---|---|---|---|---|---|
| J8 · Gripper | 1 | 8 | Yes | 2088 | 7.3 | 3.10 | Passed |
| J7 · Wrist Roll | 1 | 7 | Yes | 2017 | 7.3 | 3.10 | Passed |
| J6 · Wrist Flex | 1 | 6 | Yes | 1855 | 7.3 | 3.10 | Passed |
| J5 · Forearm Rotation | 1 | 5 | Yes | 2046 | 7.4 | 3.10 | Passed |
| J4 · Elbow Flex | 1 | 4 | Yes | 2017 | 7.3 | 3.10 | Passed |
| J3 · Shoulder Roll | 1 | 3 | Yes | 2887 | 7.2 | 3.10 | Passed |
| J2 · Shoulder Lift | 1 | 2 | Yes | 2220 | 7.3 | 3.10 | Passed |
| J1 · Shoulder Pan | 1 | 1 | Yes | 1577 | 7.4 | 3.10 | Passed |

## 4 S3 Full-arm electrical and communication tests

| Joint | ID | Position | Voltage V | Temperature °C | Status | Torque | Firmware | Over-voltage limit V | Over-temperature limit °C | Phase | Max_Acc | Judgement |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| J1 · Shoulder Pan | 1 | 831 | 7.3 | 28 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Passed |
| J2 · Shoulder Lift | 2 | 2881 | 7.3 | 27 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Passed |
| J3 · Shoulder Roll | 3 | 2298 | 7.3 | 28 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Passed |
| J4 · Elbow Flex | 4 | 761 | 7.2 | 29 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Passed |
| J5 · Forearm Rotation | 5 | 2673 | 7.3 | 28 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Passed |
| J6 · Wrist Flex | 6 | 1257 | 7.2 | 28 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Passed |
| J7 · Wrist Roll | 7 | 2120 | 7.3 | 29 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Passed |
| J8 · Gripper | 8 | 2777 | 7.2 | 28 | 0 | 0 | 3.10 | 12 | 80 | 92 | 250 | Passed |

Supply profile mini_field_7v5; firmware 3.10; voltage spread 0.1 V (recorded only). Recorded at 2026-10-23T10:51:40+08:00.

Communication stability: 60 s of continuous polling; 11631 communication polling cycles, 93048 motor-register reads, 0 failures. Polling cycles are not mechanical movements or separate tests.

## 5 S4 Joint identity and mobility

| Tested joint | Span (counts) | Motor with largest span | Runner-up span | Judgement |
|---|---|---|---|---|
| J1 · Shoulder Pan | 972 | J1 · Shoulder Pan | 134 | Passed |
| J2 · Shoulder Lift | 1811 | J2 · Shoulder Lift | 86 | Passed |
| J3 · Shoulder Roll | 3151 | J3 · Shoulder Roll | 106 | Passed |
| J4 · Elbow Flex | 1732 | J4 · Elbow Flex | 108 | Passed |
| J5 · Forearm Rotation | 2572 | J5 · Forearm Rotation | 280 | Passed |
| J6 · Wrist Flex | 904 | J6 · Wrist Flex | 249 | Passed |
| J7 · Wrist Roll | 2023 | J7 · Wrist Roll | 120 | Passed |
| J8 · Gripper | 2414 | J8 · Gripper | 51 | Passed |

Criterion: the motor with the largest span must be the tested joint and ≥ runner-up × 3; tested span ≥ 100 counts.

## 6 S5 Official calibration and consistency check

| Joint | id | drive_mode | homing_offset | range_min | range_max |
|---|---|---|---|---|---|
| J1 · Shoulder Pan | 1 | 0 | -1206 | 0 | 4095 |
| J2 · Shoulder Lift | 2 | 0 | 838 | 0 | 4095 |
| J3 · Shoulder Roll | 3 | 0 | -760 | 0 | 4095 |
| J4 · Elbow Flex | 4 | 0 | -1254 | 0 | 4095 |
| J5 · Forearm Rotation | 5 | 0 | 1279 | 0 | 4095 |
| J6 · Wrist Flex | 6 | 0 | -717 | 0 | 4095 |
| J7 · Wrist Roll | 7 | 0 | -34 | 0 | 4095 |
| J8 · Gripper | 8 | 0 | 1637 | 2047 | 3732 |

Calibration saved at 2026-10-23T15:25:57+08:00.

## 7 S6 Official-driver readout verification

| Time | Mode | Joint | Readings | Judgement |
|---|---|---|---|---|
| 2026-10-23T15:26:49+08:00 | Zero pose |  | S6.calibrated=True; S6.zero_pose=2.86; S6.gripper_closed=0 | Passed |
| 2026-10-23T15:29:13+08:00 | Gripper open |  | S6.calibrated=True; S6.gripper_open=-65 | Passed |
| 2026-10-23T15:29:54+08:00 | Sweep | J6 · Wrist Flex | S6.calibrated=True; S6.remap=145.93; S6.direction=+ | Passed |
| 2026-10-23T15:30:26+08:00 | Sweep | J7 · Wrist Roll | S6.calibrated=True; S6.remap=177.23; S6.direction=- | Passed |

Customer teleoperation command: do not copy and run it unchanged. First activate the LeRobot environment, replace `<can0>` with the Follower CAN interface and `<follower_id>` with the Follower ID, and verify that `--teleop.port` matches the Mini serial port on the customer's computer. The command can then be copied and run.

```
lerobot-teleoperate \
    --robot.type=openarm_follower --robot.port=<can0> --robot.side=left --robot.id=<follower_id> \
    --teleop.type=openarm_mini --teleop.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5959112505-if00 \
    --teleop.side=left --teleop.id=OAML2026102301
```

## 8 Release criteria

| ID | Description | Limit | Basis |
|---|---|---|---|
| S1.checklist | Preparation checklist fully confirmed, operator recorded | all | Official |
| S2.single_on_bus | Broadcast ping answered by exactly one motor, model 777 | 1 | Official |
| S2.voltage | Measured voltage within the tolerance of 7.5 V and below rated + tolerance | 1 V | Derived |
| S2.persisted | Found again at the new ID and 1 Mbps after ≥5 s power off | rescan | Derived |
| S2.joint_confirmed | Moving only this joint changes the reading by ≥ threshold (the ID sits on this joint's motor) | 100 counts | Derived |
| S3.present | IDs 1–8 all answer, model 777 | 8 | Official |
| S3.firmware_same | Same firmware on all 8 (checked by LeRobot on connect) | same | Official |
| S3.voltage | Each voltage within the tolerance of 7.5 V | 1 V | Derived |
| S3.temperature | Temperature at rest, torque off ≤ threshold | 40 °C | Derived |
| S3.status | Status register is 0 (no alarm bits) | 0 | Derived |
| S3.torque_off | Torque disabled | 0 | Derived |
| S3.comm | Continuous reads of all 8 positions, 0 failures | 60 s | Derived |
| S4.identity | When one joint is moved its travel is largest and ≥ runner-up × threshold | 3 | Derived |
| S4.span | Tested joint travel ≥ threshold | 100 counts | Derived |
| S5.precheck | Precheck: single-turn readings, predicted offset \|·\| ≤ 2047 | 2047 | Official |
| S5.saved | Official calibration printed the save marker | saved | Official |
| S5.consistent | Calibration file and EEPROM consistent 8/8, Phase=12 | 8 | Official |
| S5.consistent_power_cycled | Consistent 8/8 again after ≥5 s power off | 8 | Derived |
| S6.calibrated | Official driver reports calibrated (is_calibrated) | is_calibrated | Official |
| S6.zero_pose | At zero pose J1–J7 readings \|·\| ≤ threshold | 15 ° | Derived |
| S6.gripper_closed | Gripper closed reading ≥ threshold (near 0°) | -10 ° | Official |
| S6.gripper_open | Gripper open reading ≤ threshold (near −65°) | -50 ° | Official |
| S6.remap | Sweeping J6/J7 changes the swapped key most | joint_6<->joint_7 | Official |

## 9 Delivery note

This report covers factory tests S1–S7. Follower pairing and other project-specific tests are performed separately when required for delivery.

## 10 Sign-off

| Role | Name | Signature | Date |
|---|---|---|---|
| Tester | xlc |  |  |
| Project Lead | pengcheng |  |  |
| Reviewer |  |  |  |
