#include <SPI.h>
#include <MFRC522.h>

// Typical wiring for Arduino Uno/Nano:
// SDA/SS -> D10
// RST    -> D9
// MOSI   -> D11
// MISO   -> D12
// SCK    -> D13
constexpr uint8_t SS_PIN = 10;
constexpr uint8_t RST_PIN = 9;

MFRC522 mfrc522(SS_PIN, RST_PIN);

void setup() {
  Serial.begin(115200);
  SPI.begin();
  mfrc522.PCD_Init();

  delay(50);
  Serial.println("RFID reader ready");
  Serial.println("Present a tag...");
}

String uidToHex(const MFRC522::Uid &uid) {
  String value = "";

  for (byte i = 0; i < uid.size; i++) {
    if (uid.uidByte[i] < 0x10) {
      value += "0";
    }
    value += String(uid.uidByte[i], HEX);
  }

  value.toUpperCase();
  return value;
}

void loop() {
  if (!mfrc522.PICC_IsNewCardPresent()) {
    return;
  }

  if (!mfrc522.PICC_ReadCardSerial()) {
    return;
  }

  const String uidHex = uidToHex(mfrc522.uid);
  Serial.print("UID:");
  Serial.println(uidHex);

  // Halt PICC and stop encryption on PCD
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();

  delay(250);
}
