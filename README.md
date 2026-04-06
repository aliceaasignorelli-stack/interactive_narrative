# RFID-triggered Interactive Video (Raspberry Pi + Arduino)

This project lets you place different RFID-tagged figurines on a reader and have each tag trigger a different video on a Raspberry Pi.

## How it works

1. **Arduino + MFRC522** reads RFID tags.
2. Arduino prints tag IDs over USB serial in the format `UID:XXXXXXXX`.
3. **Raspberry Pi Python script** listens to serial input.
4. Script maps each UID to a video file and switches playback.

## Repository files added for this setup

- `arduino/rfid_reader/rfid_reader.ino`  
  Arduino sketch for MFRC522.
- `pi/rfid_video_switcher.py`  
  Pi-side serial listener + video switcher.
- `pi/tag_video_map.json`  
  Config file: serial port, player command, UID -> video map.

## Hardware wiring (MFRC522 -> Arduino Uno/Nano)

MFRC522 pin | Arduino pin
---|---
SDA (SS) | D10
SCK | D13
MOSI | D11
MISO | D12
RST | D9
3.3V | 3.3V
GND | GND

> Important: MFRC522 is a **3.3V** device.

## Raspberry Pi setup

From project root:

```bash
sudo apt update
sudo apt install -y python3-serial vlc
```

If `python3-serial` package is unavailable on your image:

```bash
python3 -m pip install pyserial
```

## Arduino setup

1. Open `arduino/rfid_reader/rfid_reader.ino` in Arduino IDE.
2. Install library: **MFRC522** by GithubCommunity.
3. Select your Arduino board and port.
4. Upload the sketch.

## Find your tag IDs first

On the Pi:

```bash
python3 pi/rfid_video_switcher.py --learn-tags
```

Scan each figurine/tag and note the printed UID values (example: `04A1B2C3D4`).

## Configure which tag plays which video

Edit `pi/tag_video_map.json`:

- `serial_port`: usually `/dev/ttyACM0` (sometimes `/dev/ttyUSB0`)
- `default_video`: video played at startup
- `video_map`: map each UID to a video filename

Example:

```json
"video_map": {
  "04A1B2C3D4": "bedroom01.mp4",
  "0499887766": "bedroom02.mp4",
  "04FFEEDDCC": "bedroom03.mp4"
}
```

## Run the RFID video switcher

```bash
python3 pi/rfid_video_switcher.py
```

When you present a mapped tag, playback switches to that tag’s video.

## Notes / troubleshooting

- If serial fails, check device:
  ```bash
  ls /dev/ttyACM* /dev/ttyUSB*
  ```
- If VLC command differs on your Pi, change `player.command` in JSON.
- Duplicate reads are rate-limited by `switch_cooldown_seconds`.
- Use absolute paths in `video_map` if your videos are stored elsewhere.
