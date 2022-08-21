## GPSD to MQTT ##

# *Purpose* #

GPSD is a program that takes the raw GPS data from a GPS reciever and displays it in the console of the machine
it's running on (Raspberry PI) in a readable format.

This skill takes the raw data from GPSD and sends it via MQTT to a MQTT broker on another device. 
This can be handy if you're wanting to record location updates while on the move to something like 
Home Assistant so that the "home" location can be automatically updated as you move. Ideal for those of us
travelling in a caravan / RV or a boat. As this skill was originally coded for sending data to 
Home Assistant it will send static configuration messages on a MQTT topic 
```homeassistant/Your_MQTT_topic/config```
and GPS values on the topic ```homeassistant/Your_MQTT_topic/attributes``` 

# *Setup on Alice* #

- Install the skill, all going well gpsdclient will get installed during skill installation. 
If for any reason it doesn't and you get a gpsdclient error install it manually with 
- ```cd ~/ProjectAlice```
- ```./venv/bin/pip3 install gpsdclient```
- Once installed, in the skill settings of alices WebUI. you have the following options to configure..

**Add**
- Your receiving MQTT broker address EG : 192.168.1.40
- Your MQTT port if its different from 1883
- Your MQTT password and username if required
- Your "GPS device name" , this is the name you give the GPS device and will become part of the mqtt topic. 
 A name like "myGPSReciever" (don't use spaces) not vital what you call it as long as its configured later in
Home Assistant the same.
- Turn on logging if you want to see debug information
- Enable "run on boot" if you want the gps data to just be sent when alice boots up
- Enable "log till stopped" if you want constant messages sent at a set interval.
Otherwise just one message will be sent if this is disabled.
- Set the "seconds between messages" for the interval between sending the location data. default is 300 seconds (5 minutes)
- gps Accuracy - set the decimal places you want to use for comparing your location of now and previous location coordinates. 
This is used for determining if the location coordinates should be written to the csv file or not. 
The higher the number the more accurate it gets and higher probability of writing minor/insignificant 
location changes to the CSV file. The default value is 3 and in general is sufficent.


# *Setup if using Home Assistant* #

Add the below to your configuration.yaml
```commandline
mqtt:
  device_tracker:
    - name: "Caravan GPS receiver"
      state_topic: "homeassistant/caravan_gps_receiver/state"
      json_attributes_topic: "homeassistant/caravan_gps_receiver/attributes"
      json_attributes_template: "{{ value_json | tojson}}"

```
remember to change the "caravan_gps_reciever" to what ever you called the device name in the alice setup

Now make a automation in Home assistant that uses ```homeassistant.set_location``` as the action. example is below

```commandline
- id: 1a06fb2f81d949c8ad6c1ff95b4d4d7c
 alias: Update Home Location
 trigger:
 - platform: mqtt
   topic: homeassistant/caravan_gps_receiver/attributes
 condition: []
 action:
 - service: homeassistant.set_location
   data_template:
     latitude: '{{ states.device_tracker.caravan_gps_receiver.attributes.latitude }}'
     longitude: '{{ states.device_tracker.caravan_gps_receiver.attributes.longitude}}'
```
again... change "caravan_gps_reciever" to what you used as devicename


# *Hardware setup* #
- Plug the USB GPS reciever into alices USB port 


# Alice control #
If you don't enable "run on boot" from the settings you can also trigger location update by asking alice to ..

- track my location
- update my location

You can also stop the tracking by asking her to 

- stop tracking my location
- stop updating my location

# Location Mapper #
For the purpose of mapping location changes in something like ```https://www.google.com/maps/d/```.
This skill will create a LocationMapper.csv file in the skills main directory with 

- Latitude
- Longitude
- The recorded time and date
- The speed
- Name

This data only gets written if longitude and latitude is different to the previous value. 
Handy for copy and pasting the csv values into a map program to record location changes
and map out where you've been.
