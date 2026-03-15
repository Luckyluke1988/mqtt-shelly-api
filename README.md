url:

ghcr.io/luckyluke1988/mqtt-shelly-api:latest


<Container version="2">
  <Name>mqtt-shelly-api</Name>
  <Repository>ghcr.io/luckyluke1988/mqtt-shelly-api:latest</Repository>
  <Network>bridge</Network>

  <Config Name="MQTT Host" Target="MQTT_HOST" Default="192.168.1.10" Mode="" Description="MQTT broker host" Type="Variable" Display="always"/>
  
  <Config Name="MQTT Port" Target="MQTT_PORT" Default="1883" Mode="" Description="MQTT broker port" Type="Variable" Display="always"/>
  
  <Config Name="MQTT Username" Target="MQTT_USERNAME" Default="root" Mode="" Description="MQTT username" Type="Variable" Display="always"/>
  
  <Config Name="MQTT Password" Target="MQTT_PASSWORD" Default="root" Mode="" Description="MQTT password" Type="Variable" Display="always"/>
  
  <Config Name="MQTT Client ID" Target="MQTT_CLIENT_ID" Default="shelly-gen4-mvp" Mode="" Description="MQTT client ID" Type="Variable" Display="advanced"/>

  <Config Name="Web UI Port" Target="8000" Default="8000" Mode="tcp" Type="Port" Display="always"/>
</Container>


Shelly connects to mqtt server
App Connetects to mqtt server
i send requerst to endpoint in app
app sends on or off command to mqtt server and server to shelly