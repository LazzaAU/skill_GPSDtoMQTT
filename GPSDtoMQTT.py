from core.base.model.AliceSkill import AliceSkill
from core.dialog.model.DialogSession import DialogSession
from core.util.Decorators import IntentHandler
import random
import json


from paho.mqtt import client as mqtt_client
from gpsdclient import GPSDClient

class GPSDtoMQTT(AliceSkill):
	"""
	Author: LazzaAU
	Description: For those that may be constantly on the move, like in a RV or a boat.
	If you install a USB GPS receiver into a raspberry Pi and want to send that data via MQTT to somewhere like Home Assistant,
	 then you can do that with this skill.
	  This will allow you to process the GPSD data to perhaps update your home location settings , graph your journey etc.
	"""
	def __init__(self):

		self.delay = float
		self.runLoop = True # True means loop will repeat, false will stop the loop
		self.mqttTopic = str
		self.clientId = f'gpsdata-{random.randint(0, 1000)}'
		super().__init__()

	# Triggers from the start tracking my location intent
	@IntentHandler('startSendingData')
	def RunGPSD(self, session: DialogSession, **_kwargs):
		self.endDialog(
			sessionId=session.sessionId,
			text=self.randomTalk(text='Starting'),
			deviceUid=session.deviceUid
		)
		self.GpsdSetup()

	# Stops reporting data from the stop tracking my location intent
	@IntentHandler('stopSendingData')
	def StopGPSD(self, session: DialogSession, **_kwargs):
		self.endDialog(
			sessionId=session.sessionId,
			text=self.randomTalk(text='Ending'),
			deviceUid=session.deviceUid
		)
		self.runLoop = False
		self.logInfo("Stopping GPSD MQTT connection")

	# Set up the Mqtt Topic and init the MQTT connection
	def GpsdSetup(self):
		"""
		- Set the MQTT topic, default to "yourGPS" if device name not set
		- set the delay between messages, default to 300 seconds if not set
		- initiate the MQTT connection
		_ move onto the publish method
		:return: nothing
		"""

		# Set the MQTT topic
		if not self.getConfig("gpsDeviceName"):
			self.mqttTopic = "homeassistant/yourGPS"
		else:
			self.mqttTopic = f"homeassistant/{self.getConfig('gpsDeviceName')}"

		# Check user has set a message delay
		if not self.getConfig(key="secondsBetweenMessages"):
			self.delay = 300
		else:
			self.delay = self.getConfig(key="secondsBetweenMessages")

		# initiate MQTT connection
		client = self.connectMqtt()
		client.loop_start()

		self.GpsPublish(client)

	# This does the code loop for sending messages every X amount of seconds
	def loopCode(self, client):
		"""
		loops through the publish method every "self.delay" seconds
		if the user has runTillStopped enabled in the settings

		:param client: The Paho MQTT Client
		:return: Nothing
		"""
		if self.runLoop:
			self.ThreadManager.doLater(
				interval=float(self.delay),
				func=self.GpsPublish,
				args=[
					client
				]
			)

	# Run the code on boot
	def onBooted(self) -> bool:
		"""
		if enabled in settings the publish event will trigger on boot up
		:return: True
		"""
		if self.getConfig(key="runOnBoot"):
			self.GpsdSetup()
			return True
		super().onBooted()

	def onStop(self):
		"""
		Stops the publish event from looping by setting self.runLoop to false
		:return: Nothing
		"""

		self.runLoop = False
		self.logInfo(f"![green](Stopping GPSD MQTT connection)")
		super().onStop()

	# MQTT disconnection capture
	def mqttDisconnect(self, client, userdata, rc):
		"""
		Captures a MQTT disconnect event and tries to reconnect
		:param client: The Paho MQTT client
		:param userdata: Not Used
		:param rc: The Paho MQTT code
		:return: nothing
		"""

		self.logInfo("GPSD Broker disconnecting reason  "  +str(rc))
		while rc != 0:
				self.logWarning("Reconnecting to GPSD broker...")
				rc = client.reconnect()


	# MQTT Connection method
	def connectMqtt(self):
		"""
		Does the actual MQTT broker connection
		:return: The Paho MQTT Client
		"""
		mqttClient = mqtt_client.Client(self.clientId)
		mqttClient.username_pw_set(self.getConfig(key="mqttUsername"), self.getConfig("mqttPassword"))
		mqttClient.on_connect = self.mqttConnectionStatus
		mqttClient.on_disconnect = self.mqttDisconnect
		mqttClient.connect(self.getConfig("receivingMqttBroker"), self.getConfig("mqttPort"))

		return mqttClient

	def mqttConnectionStatus(self, client, userdata, flags, rc):
		"""
		Informs the user when Broker connection is established or not when first connecting
		:param client: The Paho MQTT client
		:param userdata: Not Used
		:param rc: The Paho MQTT code
		:return: Nothing
		"""

		if rc == 0:
			self.logInfo("Connected to GPS MQTT Broker!........")
		else:

			self.logInfo("Failed to connect to GPS Broker, return code %d\n", rc)


	# MQTT publish method. This method is responsible for sending the MQTT message to Home Assistant
	def GpsPublish(self, client):
		"""
		- Triggers the GPSD client for GPS data, stores the required data in attributePayload
		- ConfigPayload is a static payload that Home Assistant requires
		- StatePayload is also a static payload to indicate to Home assistant the device is "Home":param client:

		This methos also Publishes the above topics to the MQTT Broker and if enabled in settings it then loops
		back on its self.

		:param client: the Paho MQTT client
		:return: Nothing
		"""

		attributePayload = self.getGpsdData() # This Sets "attributePayload" to what ever the result of getGpsdData returns (see method further down)

		if attributePayload is not None:

			# One of three messages that get sent to HA. This is the config payload and in general won't need modifying
			configPayload = {
				'state_topic': f"{self.mqttTopic}/state",
				"name": "GPS receiver",
				"payload_home": "home",
				"payload_not_home": "not_home",
				"json_attributes_topic": f"{self.mqttTopic}/attributes"
			}
			# The 3rd topic for telling Home Assistant the device is "home"
			statePayload = 'home'

			# Publish attributes to the MQTT broker as a json
			result = client.publish(f'{self.mqttTopic}/attributes', json.dumps(attributePayload))
			# Publish HA configuration data to the MQTT broker as a json
			client.publish(f'{self.mqttTopic}/config', json.dumps(configPayload))
			# Publish State data via MQTT as JSON
			client.publish(f'{self.mqttTopic}/state', json.dumps(statePayload))

			# Check for successful MQTT delivery and log/display the result
			status = result[0]

			if status == 0 :
				if self.getConfig(key="enableLogging"):
					self.logWarning(f"Data sent to the topic {self.mqttTopic}/attributes... ")
					self.logDebug(f"Sent --> `{attributePayload}` to topic ``")
					self.logWarning(f"Data sent to the topic {self.mqttTopic}/config ....")
					self.logDebug(f'{configPayload} ')

					# The message to display in the log file if successfull/failed
					self.logInfo(f'GPS Data was successfully sent')

				if self.getConfig(key="runTillStopped") and self.runLoop:
					self.loopCode(client=client)

			else:
				self.logWarning(f"Failed to send GPS data to topic {self.mqttTopic}/attributes and/or {self.mqttTopic}/config")
	
	def getGpsdData(self):
		"""
		Triggers the GPSD client and returns the required GPS data that has coordinates in it.
		- Displays the raw data to the user if selected in the settings.

		NOTE: Adjust gpsPayload to suit your devices read out as per raw GPSD data
		:return: Required GPS data in JSON format as gpsPayload
		"""
		gpsClient = GPSDClient(host="127.0.0.1") # This is where the GPSD client is running. 127.0.0.1 is the local
		# machine so you can usually leave this as it is
		if self.getConfig(key="enableLogging"):
			self.logWarning(f"Raw Data from your GPS device is ...")
		# Create json payload
		for result in gpsClient.dict_stream():

			# if you've enabled payload logging, this statement will run
			if self.getConfig(key="enableLogging"):
				self.logDebug(f"{result}")
				self.logInfo("")

			# TPV class is where you longitude and latitude data is in the gpsd output
			if result["class"] == "TPV":

				# This gpsPayload is data you want sent to HA. replace/add/remove fields as required based on the output of your receiver
				# format is :
				# 'the name of the data field' : result["the name associated with the value that gpsd ouputs"]
				# my gpsd example output = {'class': 'TPV', 'device': '/dev/ttyACM0', 'status': 2, 'mode': 2, 'time': datetime.datetime(2022, 8, 10, 1, 38, 2), 'ept': 0.005, 'lat': -xx.351406667, 'lon': xxx.5549935, 'epx': 2.387, 'epy': 2.7, 'track': 0.0, 'speed': 0.09, 'eps': 5.4}
				gpsPayload = {
					'source_type': 'gps',
					'latitude': result["lat"],
					'longitude': result["lon"],
					'speed': result["speed"],
					#'ept': result["ept"],
					#'epx': result["epx"],
					#'epy': result["epy"],
					'track': result["track"],
					#'eps': result["eps"],
					'battery_level': 100
				}
				return gpsPayload
