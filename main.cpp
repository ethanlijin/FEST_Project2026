void setup(){
    Serial.begin(9600);
}

void loop(){
    float analogValue = analogRead(AI);
    Serial.println(analogValue,3);

    delay(2);
}