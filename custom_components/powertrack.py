import logging
import homeassistant.loader as loader
from homeassistant.components import switch, notify
from homeassistant.helpers.event import track_state_change
from homeassistant.const import STATE_ON, STATE_OFF, STATE_HOME, STATE_NOT_HOME
from homeassistant.helpers.event import track_point_in_time
import homeassistant.util.dt as dt_util
import datetime

# The domain of your component. Should be equal to the name of your component.
DOMAIN = "powertrack"

# List of component names (string) your component depends upon.
DEPENDENCIES = ['mqtt','switch']


CONF_TOPIC = 'topic'
METER1_TOPIC = 'locations/MyHouse/power/emontx/1/meter/ct1'
METER2_TOPIC = 'locations/MyHouse/power/emontx/1/meter/ct2'
METER3_TOPIC = 'locations/MyHouse/power/emontx/1/meter/ct3'
POWER1_TOPIC = 'locations/MyHouse/power/emontx/1/ct1/+' 
POWER2_TOPIC = 'locations/MyHouse/power/emontx/1/ct2/+'
POWER3_TOPIC = 'locations/MyHouse/power/emontx/1/ct3/+'

#this is microseconds=(milliseconds*1000)
RED_LED_DELAY_MS = 250000

#this is seconds
CT2_DELAY = 10
CT3_DELAY = 10

#watts
#the difference between supply - load before use
CT2_BUFFER = 200
CT3_BUFFER = 200
#the load that will be used if switched on
CT2_LOAD = 1000
CT3_LOAD = 1000

def setup(hass, config):
    """Setup the component."""
    _LOGGER = logging.getLogger(__name__)

    curr_ct1_power = 0
    curr_ct2_power = 0
    curr_ct2_power = 0

    timer_ct2 = True
    timer_ct3 = True

    #are the switches in auto mode
    #auto_ct2 = True
    #auto_ct3 = True

    mqtt = loader.get_component('mqtt')
    meter1_topic = config[DOMAIN].get('meter1', METER1_TOPIC)
    meter2_topic = config[DOMAIN].get('meter2', METER2_TOPIC)
    meter3_topic = config[DOMAIN].get('meter3', METER3_TOPIC)
    
    power1_topic = config[DOMAIN].get('power1',POWER1_TOPIC)
    power2_topic = config[DOMAIN].get('power2',POWER2_TOPIC)
    power3_topic = config[DOMAIN].get('power3',POWER3_TOPIC)

    entity_id = 'powertrack'

    # Listener to be called when we receive a message.
    def message_received_m1(topic, payload, qos):
        """A new MQTT message has been received."""
        hass.states.set(meter1_topic, payload)

    def message_received_m2(topic, payload, qos):
        """A new MQTT message has been received."""
        hass.states.set(entity_id+'.meter2', payload)

    def message_received_m3(topic, payload, qos):
        """A new MQTT message has been received."""
        hass.states.set(entity_id+'.meter3', payload)

    def message_received_p1(topic, payload, qos):
        """A new MQTT message has been received."""
        hass.states.set(entity_id+'.power1', payload)
        val = int(payload)
        curr_ct1_power = val
        if val > 0:
            #mqtt.publish(hass,'cmnd/solarimmersion/power','On')
            #hass.states.set('switch.red_led','on')
            switch.turn_on(hass,'switch.red_led')
            track_point_in_time(hass, led_callback, dt_util.utcnow()+datetime.timedelta(microseconds=RED_LED_DELAY_MS))

    def message_received_p2(topic, payload, qos):
        """A new MQTT message has been received."""
        hass.states.set(entity_id+'.power2', payload)
        timer_ct2 = hass.states.get(entity_id+'.timer_ct2')
        val = int(payload)
        curr_ct2_power = val
        
        #are we in manual or auto
        state_ct2 = hass.states.is_state('input_boolean.immersion_auto',STATE_ON)
        auto_ct2 = state_ct2
        #turn on if enough power and timer allows
        #_LOGGER.error('p2','checking power')
        if (auto_ct2) and (curr_ct2_power > (CT2_LOAD+CT2_BUFFER)) and timer_ct2:
            switch.turn_on(hass,'switch.solar_immersion')
            _LOGGER.error('timer_ct2',''+str(timer_ct2) )
            hass.states.set(entity_id+'.timer_ct2',False)
            track_point_in_time(hass,ct2_callback, dt_util.utcnow()+datetime.timedelta(seconds=CT2_DELAY) ) 
            #return

        state_immersion = hass.states.is_state('switch.solar_immersion',STATE_ON)
        if (auto_ct2) and timer_ct2 and state_immersion:
            switch.turn_off(hass,'switch.solar_immersion')
            hass.states.set(entity_id+'.timer_ct2',False)
            track_point_in_time(hass,ct2_callback,dt_util.utcnow()+datetime.timedelta(seconds=CT2_DELAY) )

    def message_received_p3(topic, payload, qos):
        """A new MQTT message has been received."""
        hass.states.set(entity_id+'.power3', payload)
        val = int(payload)
        curr_ct3_power = val
        
    def led_callback(event_time):
        switch.turn_off(hass,'switch.red_led')

    def ct2_callback(event_time):
        hass.states.set(entity_id+'.timer_ct2',True)

    def ct3_callback(event_time):
        hass.states.set(entity_id+'.timer_ct3',True)

    # Subscribe our listener to a topic.
    mqtt.subscribe(hass, meter1_topic, message_received_m1)
    mqtt.subscribe(hass, meter2_topic, message_received_m2)
    mqtt.subscribe(hass, meter3_topic, message_received_m3)
    mqtt.subscribe(hass, power1_topic, message_received_p1)
    mqtt.subscribe(hass, power2_topic, message_received_p2)
    mqtt.subscribe(hass, power3_topic, message_received_p3)    



# Set the intial state
    hass.states.set(meter1_topic, 0)
    hass.states.set(entity_id+'.meter2', '0')
    hass.states.set(entity_id+'.meter3', '0')
    hass.states.set(entity_id+'.power1', '0')
    hass.states.set(entity_id+'.power2', '0')
    hass.states.set(entity_id+'.power3', '0')
    hass.states.set(entity_id+'.timer_ct2',timer_ct2)

    # Service to publish a message on MQTT.
    def set_state_service(call):
        """Service to send a message."""
        mqtt.publish(hass, topic, call.data.get('new_state'))
    def set_meter1(call):
        mqtt.publish(hass, 'a/topic', call.data.get('new_state'))

    # Register our service with Home Assistant.
    hass.services.register(DOMAIN, 'set_state', set_state_service)
    hass.services.register(DOMAIN, 'set_meter1', set_meter1)
    # Return boolean to indicate that initialization was successfully.
    return True
