# Domoticz TinyTUYA Local Plugin
#
# Author: Xenomes (xenomes@outlook.com)
# Updated: GertVersteeg1956, Nov 15th, 2024
# Description: Started adding processing of Action LSC Powerplugs with energy metering 
#
"""
<plugin key="tinytuyalocal" name="TinyTUYA (Local Control)" author="GertVersteeg1956" version="0.1" wikilink="" externallink="https://github.com/Xenomes/Domoticz-TinyTUYA-Local-Plugin.git">
    <description>
        <h2>TinyTUYA Plugin Local Controlversion Alpha 0.1</h2><br/>
        <br/>
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>On/Off control</li>
        </ul>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>All devices that have on/off state should be supported</li>
        </ul>
    </description>
    <params>
        <param field="Mode6" label="Debug" width="150px">
            <options>
                <option label="None" value="0"  default="true" />
                <option label="Python Only" value="2"/>
                <option label="Basic Debugging" value="62"/>
                <option label="Basic + Messages" value="126"/>
                <option label="Queue" value="128"/>
                <option label="Connections Only" value="16"/>
                <option label="Connections + Queue" value="144"/>
                <option label="All" value="-1"/>
            </options>
        </param>
    </params>
</plugin>
"""
try:
    import DomoticzEx as Domoticz
except ImportError:
    import fakeDomoticz as Domoticz
import tinytuya
# from tinytuya import Contrib
import subprocess
import platform
import sys
import json
import ast
import time
import base64

class BasePlugin:
    enabled = False
    def __init__(self):
        return

    def onStart(self):
        Domoticz.Log('TinyTUYA ' + Parameters['Version'] + ' plugin started')
        Domoticz.Log('TinyTuya Version:' + tinytuya.version )
        if Parameters['Mode6'] != '0':
            Domoticz.Debugging(int(Parameters['Mode6']))
            # Domoticz.Log('Debugger started, use 'telnet 0.0.0.0 4444' to connect')
            # import rpdb
            # rpdb.set_trace()
            DumpConfigToLog()
        # Domoticz.Heartbeat(10)
        onHandleThread(True)

    def onStop(self):
        Domoticz.Log('onStop called')

    def onConnect(self, Connection, Status, Description):
        Domoticz.Log('onConnect called')

    def onMessage(self, Connection, Data):
        Domoticz.Log('onMessage called')

    def onCommand(self, DeviceID, Unit, Command, Level, Color):
        Domoticz.Debug("onCommand called for Device " + str(DeviceID) + " Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level) + "', Color: " + str(Color))

        # device for the Domoticz
        dev = Devices[DeviceID].Units[Unit]
        category = getConfigItem(DeviceID, 'category')
        # Domoticz.Debug('Device ID: ' + str(DeviceID))
        # Domoticz.Debug('Category: ' + str(category))
        # Domoticz.Debug('nValue: ' + str(dev.nValue))
        # Domoticz.Debug('sValue: ' + str(dev.sValue) + ' Type ' + str(type(dev.sValue)))
        # Domoticz.Debug('LastLevel: ' + str(dev.LastLevel))
        # Domoticz.Debug('Type: ' + str(dev.Type) + ' ' + str(dev.SubType) + ' ' + str(dev.SwitchType))
        # Domoticz.Debug(str(devs))
        # Control device and update status in Domoticz
        if Command == 'Set Level':
            if dev.Type == 244 and dev.SubType == 62 and dev.SwitchType == 18:
                mode = dev.Options['LevelNames'].split('|')
                SendCommand(DeviceID, Unit, mode[int(Level / 10)])
                UpdateDevice(DeviceID, Unit, Level, 1, 0)
            else:
                SendCommand(DeviceID, Unit, Level, category)
                UpdateDevice(DeviceID, Unit, Level, 1, 0)
        elif Command == 'Set Color':
            SendCommand(DeviceID, Unit, eval(Color), category)
            UpdateDevice(DeviceID, Unit, Color, 1, 0)
        else:
            SendCommand(DeviceID, Unit, True if Command not in ['Off', 'Closed', False] else False, category)
            UpdateDevice(DeviceID, Unit, Command, 1 if Command not in ['Off', 'Closed'] else 0, 0)

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log('Notification: ' + Name + ', ' + Subject + ', ' + Text + ', ' + Status + ', ' + str(Priority) + ', ' + Sound + ', ' + ImageFile)

    def onDeviceRemoved(self, DeviceID, Unit):
        Domoticz.Log('onDeviceDeleted called')

    def onDisconnect(self, Connection):
        Domoticz.Log('onDisconnect called')

    def onHeartbeat(self):
        Domoticz.Debug('onHeartbeat called')
        # if time.time() - getConfigItem(DeviceID, 'last_update') < 10:
        #     Domoticz.Debug("onHeartbeat called skipped")
        #     return
        # Domoticz.Debug("onHeartbeat called last run: " + str(time.time() - last_update))
        onHandleThread(False)

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(DeviceID, Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(DeviceID, Unit, Command, Level, Color)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

def onHandleThread(startup):
    # Run for every device on startup and heartbeat
    try:
        if startup == True:
            global tuya
            global devs
            global last_update
            last_update = time.time()
            devs = None
            with open(Parameters['HomeFolder'] + 'devices.json') as dFile:
                devs = json.load(dFile)

        # Domoticz.Debug('Devs' + str(devs))

        # Initialize/Update devices from TUYA API
        if devs is None:
            Domoticz.Error('devices.json is missing in the plugin folder!')
            exit
        # Create devices
        for dev in devs:
            Domoticz.Debug( 'Device name=' + str(dev['name']) + ' id=' + str(dev['id']) + ' ip=' + str(dev['ip']) + ' version=' + str(dev['version'])) # ' key=' + str(dev['key']) +
            mapping = dev['mapping']
            dev_type = DeviceType(dev['category'])
            for key, value in mapping.items():
                value['dp'] = key
            code_list = [value['code'] for key, value in mapping.items()]
            Domoticz.Debug('code list = ' + str(code_list))
            if str(dev['ip']) != '':
                # tuya = tinytuya.Device(ev_id=str(dev['id']), address=str(dev['ip']), local_key=str(dev['key']), version=float(dev['version']))
                # tuya.use_old_device_list = True
                # tuya.new_sign_algorithm = True

                if startup == True:
                    Domoticz.Debug('Run Startup script')
                    if dev_type in ('light', 'fanlight', 'pirlight'):
                        pass
                        unit = 1
                        if createDevice(dev['id'], unit):
                            # Domoticz.Debug('Code List: ' + str(code_list))
                            # Create Lights
                            if ('switch_led' in code_list or 'led_switch' in code_list or 'switch_led_1' in code_list or 'switch_led_2' in code_list) and 'work_mode' in code_list and ('colour_data' in code_list or 'colour_data_v2' in code_list) and ('temp_value' in code_list or 'temp_value_v2' in code_list) and ('bright_value' in code_list or 'bright_value_v2' in code_list):
                                Domoticz.Log('Create device Light RGBWW')
                                Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=unit, Type=241, Subtype=4, Switchtype=7, Used=1).Create() #RGBWW
                            elif ('switch_led' in code_list or 'led_switch' in code_list or 'switch_led_1' in code_list or 'switch_led_2' in code_list) and 'work_mode' in code_list and ('colour_data' in code_list or 'colour_data_v2' in code_list) and ('temp_value' in code_list or 'temp_value_v2' in code_list) and not('bright_value' in code_list and 'bright_value_v2' in code_list):
                                Domoticz.Log('Create device Light RGBW')
                                Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=unit, Type=241, Subtype=1, Switchtype=7, Used=1).Create() #RGBW
                            elif ('switch_led' in code_list or 'led_switch' in code_list) and not ('work_mode' in code_list) and ('colour_data' in code_list or 'colour_data_v2' in code_list) and not('temp_value' in code_list and 'temp_value_v2' in code_list) and ('bright_value' in code_list or 'bright_value_v2' in code_list):
                                Domoticz.Log('Create device Light RGB')
                                Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=unit, Type=241, Subtype=2, Switchtype=7, Used=1).Create() #RGB
                            elif ('switch_led' in code_list or 'led_switch' in code_list) and 'work_mode' in code_list and not ('colour_data' in code_list and 'colour_data_v2' in code_list) and ('temp_value' in code_list or 'temp_value_v2' in code_list) and ('bright_value' in code_list or 'bright_value_v2' in code_list):
                                Domoticz.Log('Create device Light WWCW')
                                Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=unit, Type=241, Subtype=8, Switchtype=7, Used=1).Create() #Cold white + Warm white
                            elif ('switch_led' in code_list or 'led_switch' in code_list) and not ('work_mode' in code_list) and not ('colour_data' in code_list and 'colour_data_v2' in code_list) and not ('temp_value' in code_list and 'temp_value_v2' in code_list) and ('bright_value' in code_list or 'bright_value_v2' in code_list):
                                Domoticz.Log('Create device Light Dimmer')
                                Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=unit, Type=241, Subtype=3, Switchtype=7, Used=1).Create() #White
                            elif ('switch_led' in code_list or 'led_switch' in code_list) and not ('work_mode' in code_list) and not ('colour_data' in code_list and 'colour_data_v2' in code_list) and not ('temp_value' in code_list and 'temp_value_v2' in code_list) and not('bright_value' in code_list and 'bright_value_v2' in code_list):
                                Domoticz.Log('Create device Light On/Off')
                                Domoticz.Unit(Name=dev['name'], DeviceID=dev['id'], Unit=unit, Type=244, Subtype=73, Switchtype=7, Used=1).Create() #Dimmer
                            else:
                                Domoticz.Log('Create device Light On/Off (Unknown Light Device)')
                                Domoticz.Unit(Name=dev['name'] + ' (Unknown Light Device)', DeviceID=dev['id'], Unit=unit, Type=244, Subtype=73, Switchtype=0, Used=1).Create() #On/Off
                    elif dev_type in ('Socket'):
                        Domoticz.Debug('Socket found')
                        for item in mapping.values():
                            unit = int(item['dp'])
                            if  createDevice(dev['id'], unit):
                                if item['code'] in [f'switch{i}' for i in range(1, 9)] + [f'switch_{i}' for i in range(1, 9)] + ['switch', 'fan_switch', 'window_check', 'child_lock', 'muffling', 'light', 'colour_switch', 'anion', 'switch_charge', 'laser_switch', 'doorcontact', 'doorcontact_state', 'door_control_1', 'door_state_1', 'smartlock', 'position', 'switch_pir', 'fan_speed', 'MachineRainMode']:
                                    Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=244, Subtype=73, Switchtype=0, Used=1).Create() #Contact
                                elif item['code'] in ['countdown_1']:
                                    Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=243, Subtype=31,  Used=1).Create() #Contact
                                elif item['code'] in ['cur_voltage']:
                                    Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=243, Subtype=8,  Used=1).Create() #Contact
                                elif item['code'] in ['add_ele', 'ActivePower', 'ActivePowerA', 'ActivePowerB', 'ActivePowerC', 'phase_a', 'total_power']:
                                    Domoticz.Log('Create Power device')
                                    Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=243, Subtype=29, Used=1).Create() #kWh
                                elif item['code'] in ['cur_current', 'cmp_cur', 'leakage_current', 'Current']:
                                    Domoticz.Log('Create Amperes device')
                                    the_values = item['values']
                                    if the_values.get('unit') != 'A':
                                        options = {}
                                        options['Custom'] = '1;'+ the_values.get('unit')
                                        Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=243, Subtype=31, Switchtype=0, Used=1).Create() #Custom Sensor
                                    else:
                                        Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=243, Subtype=23, Switchtype=0, Used=1).Create() #Current (Single)
                                elif item['code'] in ['cur_power']:
                                    Domoticz.Log('Create Watt device')
                                    Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=248, Subtype=1, Switchtype=0, Used=1).Create() #Electric Usage
                                elif item['code'] in ['add_ele']:
                                    Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=243, Subtype=31,  Used=1).Create() #Contact
                    else:
                        Domoticz.Debug ('dev_type ' + dev_type + ' not implemented yet!')

                    # elif dev_type not in ('light', 'fanlight', 'pirlight'):
#                    for item in mapping.values():
#                        # Domoticz.Debug(str(item['code']))
#                        unit = int(item['dp'])
#                        if  createDevice(dev['id'], unit):
#
#                            # Create Switch
#                            if item['code'] in [f'switch{i}' for i in range(1, 9)] + [f'switch_{i}' for i in range(1, 9)] + ['switch', 'fan_switch', 'window_check', 'child_lock', 'muffling', 'light', 'colour_switch', 'anion', 'switch_charge', 'laser_switch', 'doorcontact', 'doorcontact_state', 'door_control_1', 'door_state_1', 'smartlock', 'position', 'switch_pir', 'fan_speed', 'MachineRainMode']:
                    #             Domoticz.Log('Create device Switch')
                    #             if item['code'] in ['doorcontact', 'doorcontact_state', 'door_control_1', 'door_state_1', 'smartlock']:
                    #                 Domoticz.Log('Create Doorcontact device')
                    #                 Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=244, Subtype=73, Switchtype=11, Used=1).Create() #Contact
                    #             elif item['code'] in ['position']:
                    #                 Domoticz.Log('Create Cover device')
                    #                 Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=244, Subtype=73, Switchtype=21, Used=1).Create() #Blinds Percentage With Stop
                    #             elif item['code'] in ['switch_pir']:
                    #                 Domoticz.Log('Create Motion Sensor device')
                    #                 Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=244, Subtype=73, Switchtype=8, Used=1).Create() #Motion Sensor
                    #             elif item['code'] in ['laser_bright',  'fan_speed']:
                    #                 Domoticz.Log('Create Dimmer device')
                    #                 Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=244, Subtype=73, Switchtype=7, Used=1).Create() #Dimmer
                    #             else:
                    #                 Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=244, Subtype=73, Switchtype=0, Used=1).Create() #On/Off

                    #         # Create Selection Switch
                    #         elif item['code'] in ['mode', 'work_mode', 'speed', 'fan_direction', 'Alarmtype', 'AlarmPeriod', 'alarm_state', 'status', 'alarm_volume', 'alarm_lock', 'cistern', 'suction', 'cistern', 'fan_speed_enum', 'dehumidify_set_value', 'device_mode', 'pir_sensitivity', 'manual_feed', 'manual_feed', 'feed_state', 'feed_report', 'alarm_lock', 'switch_mode', 'laser_switch', 'defrost_state', 'compressor_state', 'MachineControlCmd'] + [f'switch{i}_value' for i in range(1, 9)] + [f'switch_type_{i}' for i in range(1, 9)]:
                    #             Domoticz.Log('Create Selection device')
                    #             the_values = item['values']
                    #             mode = ['off']
                    #             mode.extend(the_values.get('range'))
                    #             options = {}
                    #             options['LevelOffHidden'] = 'true'
                    #             options['LevelActions'] = ''
                    #             options['LevelNames'] = '|'.join(mode)
                    #             options['SelectorStyle'] = '0' if len(mode) < 5 else '1'
                    #             Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=244, Subtype=62, Switchtype=18, Options=options, Image=9, Used=1).Create() #Selector Switch

                    #         # Powermetering
                    #         elif item['code'] in ['ActivePowerA'] in code_list and ['ActivePowerB'] in code_list and ['ActivePowerC']:
                    #             Domoticz.Log('Create Current (3 Phase) device')
                    #             Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=89, Subtype=1, Used=1).Create() #Ampere (3 Phase)
                    #         elif item['code'] in ['cur_power', 'cur_power', 'power_a', 'power_b']:
                    #             Domoticz.Log('Create Watt device')
                    #             Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=248, Subtype=1, Switchtype=0, Used=1).Create() #Electric Usage
                    #         elif item['code'] in ['cur_current', 'cmp_cur', 'leakage_current', 'Current']:
                    #             Domoticz.Log('Create Amperes device')
                    #             the_values = item['values']
                    #             if the_values.get('unit') != 'A':
                    #                 options = {}
                    #                 options['Custom'] = '1;'+ the_values.get('unit')
                    #                 Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=243, Subtype=31, Switchtype=0, Used=1).Create() #Custom Sensor
                    #             else:
                    #                 Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=243, Subtype=23, Switchtype=0, Used=1).Create() #Current (Single)
                    #         elif item['code'] in ['voltage_a', 'cur_voltage', 'cur_voltage']:
                    #             Domoticz.Log('Create Volt device')
                    #             Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=243, Subtype=8, Switchtype=0, Used=1).Create() #Voltage
                    #         elif item['code'] in ['add_ele', 'ActivePower', 'ActivePowerA', 'ActivePowerB', 'ActivePowerC', 'phase_a', 'total_power', 'cur_power']:
                    #             Domoticz.Log('Create Power device')
                    #             Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=243, Subtype=29, Used=1).Create() #kWh
                    #         elif item['code'] in ['phase_a'] and item['type'] in ['Raw']:
                    #             Domoticz.Unit(Name=dev['name'] + ' (A)', DeviceID=dev['id'], Unit=100 + unit, Type=243, Subtype=23, Used=1).Create()
                    #             Domoticz.Unit(Name=dev['name'] + ' (W)', DeviceID=dev['id'], Unit=101 + unit, Type=248, Subtype=1, Used=1).Create()
                    #             Domoticz.Unit(Name=dev['name'] + ' (V)', DeviceID=dev['id'], Unit=102 + unit, Type=243, Subtype=8, Used=1).Create()
                    #             Domoticz.Unit(Name=dev['name'] + ' (kWh)', DeviceID=dev['id'],Unit=103 + unit, Type=243, Subtype=29, Used=1).Create()

                    #         # Create Sensors
                    #         elif item['code'] in ['temp_current', 'intemp', 'outtemp', 'whjtemp', 'cmptemp', 'wttemp', 'hqtemp', 'va_temperature''sub1_temp', 'sub2_temp', 'sub3_temp', 'Temperature', 'temp_indoor', 'temperature', 'temp_top', 'temp_bottom',]:
                    #             Domoticz.Log('Create Temperature device')
                    #             Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=80, Subtype=5, Used=1).Create() #Temperature sensor
                    #         elif item['code'] in ['va_humidity', 'sub1_hum', 'sub2_hum', 'sub3_hum', 'humidity_indoor']:
                    #             Domoticz.Log('Create Humidity device')
                    #             Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=81, Subtype=1, Used=1).Create() #Humidity sensor
                    #         elif item['code'] in ['electricity_left', 'filter']:
                    #             Domoticz.Log('Create Percentage device')
                    #             Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=243, Subtype=6, Used=1).Create() #Percentage
                    #         elif item['code'] in ['bright_value']:
                    #             Domoticz.Log('Create Lux device')
                    #             Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=246, Subtype=1, Switchtype=11, Used=1).Create() #Lux
                    #         elif item['code'] in ['co2_value', 'pm25', 'roll_brush', 'edge_brush', 'RH_value', 'RH_threshold', 'atmosphere', 'pm10', 'pm25_value', 'voc_value', 'ch2o_value', 'water_flow', 'dc_fan_speed', 'cmp_act_frep']:
                    #             Domoticz.Log('Create Custom device')
                    #             the_values = item['values']
                    #             options = {}
                    #             options['Custom'] = the_values.get('unit')
                    #             Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=243, Subtype=31, Options=options, Used=1).Create() #Custom Sensor
                    #         elif item['code'] in ['air_quality_index', 'direction_a', 'direction_b', 'gateway', 'status', 'fault', 'multifunctionalarm', 'air_quality', 'watersensor_state', 'MachineStatus', 'MachineWarning', 'MachineError']:
                    #             Domoticz.Log('Create Text device')
                    #             Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=243, Subtype=19, Image=13, Used=1).Create() #Text

                    #         # Create SetPoint device
                    #         elif item['code'] in ['set_temp', 'temp_set', 'cook_temperature', 'wth_stemp', 'ach_stemp', 'aircond_temp_diff', 'wth_temp_diff', 'acc_stemp', 'cook_temperature']:
                    #             the_values = item['values']
                    #             options = {}
                    #             options['ValueStep'] = the_values.get('step')
                    #             options['ValueMin'] = the_values.get('min')
                    #             options['ValueMax'] = the_values.get('max')
                    #             options['ValueUnit'] = the_values.get('unit')
                    #             Domoticz.Unit(Name=dev['name'] + ' (' + str(item['code']) + ')', DeviceID=dev['id'], Unit=unit, Type=242, Subtype=1, Options=options, Used=1).Create() #Set Point
                    #         else:
                    #             Domoticz.Debug('No mapping found for device: ' + str(dev['name']) + ' sub device: ' + str(item['code']))

                    # setConfigItem(dev['id'], {'unit': unit, 'category': dev_type, 'key': dev['key'], 'ip': dev['ip'], 'version': dev['version'], 'last_update': 0})

                else:
                    # update devices in Domoticz
                    Domoticz.Debug('Update devices in Domoticz')
                    # status Domoticz
                    # sValue = Devices[dev['id']].Units[1].sValue
                    # nValue = Devices[dev['id']].Units[1].nValue
                    tuya = tinytuya.Device(dev_id=str(dev['id']), address=str(dev['ip']), local_key=str(dev['key']), version=str(dev['version']), connection_timeout=5, connection_retry_limit=1)
                    if float(time.time()) > float(getConfigItem(dev['id'], 'last_update')):
                        tuya.detect_available_dps()
                        tuya.detect_available_dps() # Two times for detection bulb devices
                        tuyastatus = tuya.status()  # tuyastatus is a dict
#                        Domoticz.Debug ('Device type = ' + dev_type + ' Device category = ' + str(dev['category']))
#                        Domoticz.Debug('=========tuyastatus: ' + str(tuyastatus))
                        # Domoticz.Debug('dev: ' + str(dev))
                        unit = 1
                        if 'Device Unreachable' in str(tuyastatus):
                            Domoticz.Error('Device :' + dev['id'] + ' is Offline!')
                            # setConfigItem(dev['id'], {'last_update': time.time() + 300})
                            UpdateDevice(dev['id'], unit, 'Off', 0, 1)
                        else:
                            for item in mapping.values():
#                                Domoticz.Debug( 'Item code ' + str(item['code']))
                                unit = int(item['dp'])
                                values = tuyastatus.get('dps')  # switchvalues is also a dict
#                                Domoticz.Debug (str(values))
                                currentstatus = values.get(str(unit))
                                if  createDevice(dev['id'], unit) == False: # does device exist?
                                    if item['code'] in [f'switch{i}' for i in range(1, 9)] + [f'switch_{i}' for i in range(1, 9)] + ['switch', 'fan_switch', 'window_check', 'child_lock', 'muffling', 'light', 'colour_switch', 'anion', 'switch_charge', 'laser_switch', 'doorcontact', 'doorcontact_state', 'door_control_1', 'door_state_1', 'smartlock', 'position', 'switch_pir', 'fan_speed', 'MachineRainMode']:
#                                        Domoticz.Debug('Update device Switch')
                                        UpdateDevice(dev['id'], unit, str(currentstatus), 0 if currentstatus == False else 1, 0)
                                    elif item['code'] in ['countdown_1']:
#                                        Domoticz.Debug('Update timeout counter')
                                        UpdateDevice(dev['id'], unit, str(currentstatus), int(currentstatus),0 )
                                    elif item['code'] in ['cur_voltage']:
                                        #Domoticz.Debug('Update current voltage to ' + str(float(currentstatus)/10.))
                                        UpdateDevice(dev['id'], unit, str(float(currentstatus)/10.), 0,0 )
                                    elif item['code'] in ['cur_current']:
                                        #Domoticz.Debug('Update current current to ' + str(float(currentstatus)/1000.))
                                        UpdateDevice(dev['id'], unit, str(float(currentstatus)/1000.), 0,0 )
                                    elif item['code'] in ['cur_power']:
                                        #Domoticz.Debug('Update current power to ' + str(float(currentstatus)/10.))
                                        UpdateDevice(dev['id'], unit, str(float(currentstatus)/10.), 0,0 )
                                    elif item['code'] in ['add_ele']:
#                                        Domoticz.Debug('Update add ele')
                                        UpdateDevice(dev['id'], unit, str(currentstatus), int(currentstatus),0 )
                                    else:
                                        Domoticz.Debug (  item['code'] + ' = ' + str(currentstatus))

                                    
#                                    else:
#                                        Domoticz.Debug(str(item['code']) + ' is no switch device!')
                                else:
                                    Domoticz.Debug
#                            #Domoticz.Debug('Type: ' + str(dev_type))
#                            if dev_type in ('light', 'fanlight', 'pirlight'):
#                                tuyastatus_dps = tuyastatus.get('dps','Key not found')
#                                if tuyastatus_dps != 'Key not found':
#                                    UpdateDevice(dev['id'], unit, True if bool(tuyastatus_dps['1']) == True else False, 0 if bool(tuyastatus['dps'][str(unit)]) == False else 1, 0)
#                            # if dev_type not in ('light', 'pirlight'):
#                            # Domoticz.Debug(str(mapping.values()))
#                            for item in mapping.values():
#                                #Domoticz.Debug('Item' + str(item))
#                                try:
#                                    unit = int(item['dp'])
#                                    try:
#                                        dtype = Devices[dev['id']].Units[unit]
#                                    except:
#                                        pass
#                                    # Update Switch
#                                    # Domoticz.Debug('Unit: ' + str(unit))
#                                    tuyastatus_dps = tuyastatus.get('dps','Key not found')
#                                    if tuyastatus_dps == 'Key not found':
#                                        tuyastatus_value = 'Key not found'
#                                    else:
#                                        tuyastatus_value = tuyastatus_dps.get(unit, 'Key not found')
#                                    # Domoticz.Debug('tuyastatus: ' + str(tuyastatus_value))
#                                    if createDevice(dev['id'], unit) == False and unit is not None and tuyastatus_value != 'Key not found':
#                                        currentstatus = get_scale(tuyastatus_value, str(item))
#                                        Domoticz.Debug('Unit: ' + str(unit) + ' Currentstatus: ' + str(currentstatus))
#                                        Domoticz.Debug('dtype: ' + str(dtype.Type) + ' ' + str(dtype.SubType) + ' ' + str(dtype.SwitchType) + ' ' + str(item['values']))
#                                        Domoticz.Debug('Item: ' + str(item['code']))
#                                        if str(item['code']) in ('switch', 'switch_1', 'switch_2'):
#                                            UpdateDevice(dev['id'], unit, currentstatus, 0 if currentstatus == False else 1, 0)
#                                        elif str(item['code']) in ['phase_a'] and str(item['type']) in ['Raw']:
#                                            decoded_data = base64.b64decode(currentstatus)
#                                            # Extract voltage, current, and power data
#                                            currentvoltage = int.from_bytes(decoded_data[:2], byteorder='big') * 0.1
#                                            currentcurrent = int.from_bytes(decoded_data[2:5], byteorder='big') * 0.001
#                                            currentpower = int.from_bytes(decoded_data[5:8], byteorder='big')
#                                            UpdateDevice(dev['id'], 100 + unit, str(currentcurrent), 0, 0)
#                                            UpdateDevice(dev['id'], 101 + unit, str(currentpower), 0, 0)
#                                            UpdateDevice(dev['id'], 102 + unit, str(currentvoltage), 0, 0)
#                                            lastupdate = (int(time.time()) - int(time.mktime(time.strptime(Devices[dev['id']].Units[103 + unit].LastUpdate, '%Y-%m-%d %H:%M:%S'))))
#                                            lastvalue = Devices[dev['id']].Units[103 + unit].sValue if len(Devices[dev['id']].Units[103 + unit].sValue) > 0 else '0;0'
#                                            UpdateDevice(dev['id'], 103 + unit, str(currentpower) + ';' + str(float(lastvalue.split(';')[1]) + ((currentpower) * (lastupdate / 3600))) , 0, 0, 1)
#                                        elif dtype.Type == 244 and dtype.SubType == 62 and dtype.SwitchType == 18:
#                                            mode = ['off']
#                                            mode.extend(item['values']['range'])
#                                            # Domoticz.Debug('Mode: ' + str(mode))
#                                            UpdateDevice(dev['id'], unit, int(mode.index(str(currentstatus)) * 10), 1, 0)
#                                        elif dtype.Type == 243 and dtype.SubType == 19 and dtype.SwitchType == 13:
#                                            mode = ['no fault']
#                                            if item['type'] == 'Bitmap':
#                                                mode.extend(item['values']['label'])
#                                                currentmode = mode[currentstatus].replace("_", " ").capitalize()
#                                            else:
#                                                mode.extend(item['values']['range'])
#                                                currentmode = mode[currentstatus].replace("_", " ").capitalize()
#                                            UpdateDevice(dev['id'], unit, str(currentmode), 1, 0)
#                                        else:
#                                            UpdateDevice(dev['id'], unit, currentstatus, 0 if currentstatus == False else 1, 0)
#                                        battery_device(unit, item['code'], currentstatus)
#                                    else:
#                                        #currentstatus = get_scale(tuyastatus_value, str(item))
#                                        Domoticz.Debug('Unit: ' + str(unit) + ' Currentstatus: ' + str(tuyastatus_value))
#                                        Domoticz.Debug('dtype: ' + str(dtype.Type) + ' ' + str(dtype.SubType) + ' ' + str(dtype.SwitchType) + ' ' + str(item['values']))
#                                        Domoticz.Debug('Item: ' + str(item['code']))
#                                        
#                                except Exception as err:
#                                    Domoticz.Error('handleThread: ' + str(err)  + ' line ' + format(sys.exc_info()[-1].tb_lineno))
#                                except:
#                                    pass
#                                    # Domoticz.Debug('No update mapping for ' + item['code'] + ' skipped')



    except Exception as err:
        Domoticz.Error('handleThread: ' + str(err)  + ' line ' + format(sys.exc_info()[-1].tb_lineno))

# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for DeviceName in Devices:
        Device = Devices[DeviceName]
        Domoticz.Debug("Device ID:       '" + str(Device.DeviceID) + "'")
        Domoticz.Debug("--->Unit Count:      '" + str(len(Device.Units)) + "'")
        for UnitNo in Device.Units:
            Unit = Device.Units[UnitNo]
            Domoticz.Debug("--->Unit:           " + str(UnitNo))
            Domoticz.Debug("--->Unit Name:     '" + Unit.Name + "'")
            Domoticz.Debug("--->Unit nValue:    " + str(Unit.nValue))
            Domoticz.Debug("--->Unit sValue:   '" + Unit.sValue + "'")
            Domoticz.Debug("--->Unit LastLevel: " + str(Unit.LastLevel))
    return

# Select device type from category
def DeviceType(category, product_id=None):
    'convert category to device type'
    'https://github.com/tuya/tuya-home-assistant/wiki/Supported-Device-Category'
    if product_id == 'uoa3mayicscacseb' or product_id == 'igtakqsfhbr7qsp7':
        result = 'cover'
    elif product_id == 'chfpey4klfcp1ipl':
        result = 'dimmer'
    elif category in {'kg', 'pc', 'tdq', 'znjdq', 'szjqr', 'aqcz'}:
        result = 'switch'
    elif category in {'cz'}:
        result = 'Socket'    
    elif category in {'dj', 'dd', 'dc', 'fwl', 'xdd', 'fwd', 'jsq', 'tyndj'}:
        result = 'light'
    elif category in {'tgq', 'tgkg'}:
        result = 'dimmer'
    elif category in {'cl', 'clkg', 'jdcljqr'}:
        result = 'cover'
    elif category in {'qn'}:
        result = 'heater'
    elif category in {'wk', 'wkf', 'mjj', 'wkcz', 'kt','hwktwkq', 'ydkt'}:
        result = 'thermostat'
    elif category in {'wsdcg', 'co2bj', 'hjjcy', 'qxj', 'ldcg', 'swtz', 'zwjcy'}:
        result = 'sensor'
    elif category in {'rs'}:
        result = 'heatpump'
    elif category in {'znrb'}:
        result = 'smartheatpump'
    elif category in {'sp'}:
        result = 'doorbell'
    elif category in {'fs'}:
        result = 'fan'
    elif category in {'fsd'}:
        result = 'fanlight'
    elif category in {'sgbj'}:
        result = 'siren'
    elif category in {'wnykq'}:
        result = 'smartir'
    elif category in {'zndb', 'dlq'}:
        result = 'powermeter'
    elif category in {'wg2', 'wfcon'}:
        result = 'gateway'
    elif category in {'mcs'}:
        result = 'doorcontact'
    elif category in {'gyd'}:
        result = 'pirlight'
    elif category in {'qt','ywbj'}:
        result = 'smokedetector'
    elif category in {'ckmkzq'}:
        result = 'garagedooropener'
    elif category in {'cwwsq'}:
        result = 'feeder'
    elif category in {'sj'}:
        result = 'waterleak'
    elif category in {'pir'}:
        result = 'presence'
    elif category in {'sfkzq'}:
        result = 'irrigation'
    elif category in {'wxkg'}:
        result = 'wswitch'
    elif category in {'dgnbj'}:
        result = 'lightsensor'
    elif category in {'xktyd'}:
        result = 'starlight'
    elif category in {'ms'}:
        result = 'smartlock'
    elif category in {'cs'}:
        result = 'dehumidifier'
    elif category in {'sd'}:
        result = 'vacuum'
    elif category in {'mal'}:
        result = 'multifunctionalarm'
    elif category in {'kj'}:
        result = 'purifier'
    elif category in {'bh'}:
        result = 'smartkettle'
    elif category in {'gcj'}:
        result = 'mower'
    elif category in {'hps'}:
        result = 'human_presence'
    elif category in {'infrared_ac'}:
        result = 'infrared_ac'
    elif 'infrared_' in category: # keep it last
        result = 'infrared'
    else:
        result = 'unknown'
    return result

# # Select device type from category
# def DeviceType(category):
#     'convert category to device type'
#     'https://github.com/tuya/tuya-home-assistant/wiki/Supported-Device-Category'
#     if category in {'kg', 'cz', 'pc', 'tdq', 'znjdq', 'szjqr', 'aqcz'}:
#         result = 'switch'
#     elif category in {'dj', 'dd', 'dc', 'fwl', 'xdd', 'fwd', 'jsq', 'tyndj'}:
#         result = 'light'
#     elif category in {'tgq', 'tgkg'}:
#         result = 'dimmer'
#     elif category in {'cl', 'clkg', 'jdcljqr'}:
#         result = 'cover'
#     elif category in {'qn'}:
#         result = 'heater'
#     elif category in {'wk', 'wkf', 'mjj', 'wkcz', 'kt','hwktwkq', 'ydkt'}:
#         result = 'thermostat'
#     elif category in {'wsdcg', 'co2bj', 'hjjcy', 'qxj', 'ldcg', 'swtz', 'zwjcy'}:
#         result = 'sensor'
#     elif category in {'rs'}:
#         result = 'heatpump'
#     elif category in {'znrb'}:
#         result = 'smartheatpump'
#     elif category in {'sp'}:
#         result = 'doorbell'
#     elif category in {'fs'}:
#         result = 'fan'
#     elif category in {'fsd'}:
#         result = 'fanlight'
#     elif category in {'sgbj'}:
#         result = 'siren'
#     elif category in {'wnykq'}:
#         result = 'smartir'
#     elif category in {'zndb', 'dlq'}:
#         result = 'powermeter'
#     elif category in {'wg2', 'wfcon'}:
#         result = 'gateway'
#     elif category in {'mcs'}:
#         result = 'doorcontact'
#     elif category in {'gyd'}:
#         result = 'pirlight'
#     elif category in {'qt','ywbj'}:
#         result = 'smokedetector'
#     elif category in {'ckmkzq'}:
#         result = 'garagedooropener'
#     elif category in {'cwwsq'}:
#         result = 'feeder'
#     elif category in {'sj'}:
#         result = 'waterleak'
#     elif category in {'pir'}:
#         result = 'presence'
#     elif category in {'sfkzq'}:
#         result = 'irrigation'
#     elif category in {'wxkg'}:
#         result = 'wswitch'
#     elif category in {'dgnbj'}:
#         result = 'lightsensor'
#     elif category in {'xktyd'}:
#         result = 'starlight'
#     elif category in {'ms'}:
#         result = 'smartlock'
#     elif category in {'cs'}:
#         result = 'dehumidifier'
#     elif category in {'sd'}:
#         result = 'vacuum'
#     elif category in {'mal'}:
#         result = 'multifunctionalarm'
#     elif category in {'kj'}:
#         result = 'purifier'
#     elif category in {'bh'}:
#         result = 'smartkettle'
#     elif category in {'gcj'}:
#         result = 'mower'
#     elif category in {'infrared_ac'}:
#         result = 'infrared_ac'
#     elif 'infrared_' in category: # keep it last
#         result = 'infrared'
#     else:
#         result = 'unknown'
#     return result

def UpdateDevice(ID, Unit, sValue, nValue, TimedOut, AlwaysUpdate = 0):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if str(Devices[ID].Units[Unit].sValue) != str(sValue) or str(Devices[ID].Units[Unit].nValue) != str(nValue) or str(Devices[ID].TimedOut) != str(TimedOut) or AlwaysUpdate == 1:
        if sValue == None:
            sValue = Devices[ID].Units[Unit].sValue
        if type(sValue) == int or type(sValue) == float:
            Devices[ID].Units[Unit].LastLevel = sValue
        elif type(sValue) == dict:
            Devices[ID].Units[Unit].Color = json.dumps(sValue)
        Devices[ID].Units[Unit].sValue = str(sValue)
        Devices[ID].Units[Unit].nValue = nValue
        Devices[ID].TimedOut = TimedOut
        Devices[ID].Units[Unit].Update(Log=True)

        Domoticz.Debug('Update device value: ' + str(ID) + ' Unit: ' + str(Unit) + ' sValue: ' +  str(sValue) + ' nValue: ' + str(nValue) + ' TimedOut=' + str(TimedOut))
    return

def SendCommand(ID, Unit, Status, Type = ''):
    Domoticz.Debug('SendCommand =  ID:' + str(ID) + ' IP:' + str(getConfigItem(ID, 'ip'))  + ' Type:' +  str(Type) + ' Status:' +  str(Status) + ' Status Type:' +  str(type(Status)) + ' Version:' + str(getConfigItem(ID, 'version')))
    if Type == 'light':
        selected_device = next((dev for dev in devs if dev['id'] == str(ID)), None)
        item = selected_device['mapping'][str(Unit)]
        Status = get_scale(Status, item)
        Domoticz.Debug('Status: ' + str(Status))
        tuya = tinytuya.BulbDevice(dev_id=str(ID), address=str(getConfigItem(ID, 'ip')), local_key=str(getConfigItem(ID, 'key')), version=str(getConfigItem(ID, 'version')), connection_timeout=5, connection_retry_limit=1)
        tuya.detect_available_dps()
        # tuya = tinytuya.BulbDevice(str(ID), getConfigItem(ID, 'ip'), getConfigItem(ID, 'key'))
        # tuya.set_version(str(getConfigItem(ID, 'version')))
        if type(Status) == int or type(Status) == float:
            # Domoticz.Debug('SendCommand: brightness')
            tuya.turn_on(switch=Unit)
            tuya.set_brightness_percentage(Status)
        elif type(Status) == dict:
            if Status['m'] == 2:
                # Domoticz.Debug('SendCommand: colourtemp')
                tuya.turn_on()
                tuya.set_colourtemp(Status['cw'])
            if Status['m'] == 3:
                # Domoticz.Debug('SendCommand: colour')
                # Domoticz.Debug('Colour: r:' + str(Status['r']) + ' g:' + str(Status['g']) + ' b:' + str(Status['r']))
                tuya.turn_on()
                tuya.set_colour(Status['r'], Status['g'], Status['b'])
        elif Status == True:
            # Domoticz.Debug('SendCommand: On')
            tuya.turn_on()
        elif Status == False:
            # Domoticz.Debug('SendCommand: Off')
            tuya.turn_off()
        Domoticz.Debug('Command send to tuya BulbDevice: ' + str(ID) + ", " + str({'commands': [{'Type': Type, 'value': Status}]}))
    else:
        selected_device = next((dev for dev in devs if dev['id'] == str(ID)), None)
        item = selected_device['mapping'][str(Unit)]
        Status = get_scale(Status, item)
        tuya = tinytuya.Device(dev_id=str(ID), address=str(getConfigItem(ID, 'ip')), local_key=str(getConfigItem(ID, 'key')), version=str(getConfigItem(ID, 'version')), connection_timeout=5, connection_retry_limit=1)
        tuya.detect_available_dps()
        payload = tuya.generate_payload(tinytuya.CONTROL_NEW, {Unit: Status})
        tuya.send(payload)
        Domoticz.Debug('Command send to tuya Device: ' + str(ID) + ", " + str({'commands': [{'dsp': Unit, 'value': Status}]}))

def searchCode(Item, Functions):
    for OneItem in Functions:
        if Item == OneItem:
            return True
        else:
            return False
    # Domoticz.Debug("searchCodeActualFunction unable to find " + str(Item) + " in " + str(Function))
    return

def createDevice(ID, Unit):
    if ID in Devices:
        if Unit in Devices[ID].Units:
            value = False
        else:
            value = True
    else:
        value = True

    return value

def battery_device(ID, ResultValue, StatusDeviceTuya):
    # Battery_device
    if searchCode('battery_state', ResultValue) or searchCode('battery', ResultValue) or searchCode('va_battery', ResultValue) or searchCode('battery_percentage', ResultValue):
        if searchCode('battery_state', ResultValue):
            if StatusDeviceTuya == 'high':
                currentbattery = 100
            if StatusDeviceTuya == 'middle':
                currentbattery = 50
            if StatusDeviceTuya == 'low':
                currentbattery = 5
        if searchCode('BatteryStatus', ResultValue):
            if int(StatusDeviceTuya) == 1:
                currentbattery = 100
            elif int(StatusDeviceTuya) == 2:
                currentbattery = 50
            elif int(StatusDeviceTuya) == 3:
                currentbattery = 5
            else:
                currentbattery = 100
        if searchCode('battery', ResultValue):
            currentbattery = StatusDeviceTuya * 10
        if searchCode('va_battery', ResultValue):
            currentbattery = StatusDeviceTuya
        if searchCode('battery_percentage', ResultValue):
            currentbattery = StatusDeviceTuya
        if searchCode('residual_electricity', ResultValue):
            currentbattery = StatusDeviceTuya
        for unit in Devices[ID].Units:
            if str(currentbattery) != str(Devices[ID].Units[unit].BatteryLevel):
                Devices[ID].Units[unit].BatteryLevel = currentbattery
                Devices[ID].Units[unit].Update()
    return

def online_offline(ID, StatusDeviceTuya):
    for unit in Devices[ID].Units:
        # Domoticz.Debug(str(ID) + '   ' + str(StatusDeviceTuya))
        if str(StatusDeviceTuya) != str(Devices[ID].TimedOut):
            Devices[ID].TimedOut = StatusDeviceTuya
            Devices[ID].Units[unit].Update()
    return

def nextUnit(ID):
    unit = 1
    while unit in Devices(ID) and unit < 255:
        unit = unit + 1
    return unit

# def convert_to_correct_type(str_value, item):
#     str_value = get_scale(str_value, item)
#     Domoticz.Debug('str_value: ' + str(str_value))
#     if isinstance(str_value, dict):
#         return str_value
#     try:
#         # Try converting to int
#         return int(str_value)
#     except ValueError:
#         try:
#             # Try converting to float
#             return float(str_value)
#         except ValueError:
#             try:
#                 # Try converting to bool
#                 if str_value.lower() == "true":
#                     return True
#                 elif str_value.lower() == "false":
#                     return False
#                 else:
#                     # If none of the above, try decoding as JSON
#                     return json.loads(str_value)
#             except (ValueError, SyntaxError, json.JSONDecodeError):
#                 try:
#                     # Try converting to list
#                     return list(ast.literal_eval(str_value))
#                 except (ValueError, SyntaxError):
#                     # If all attempts fail, return the original string
#                     return str_value

def ping_ok(sHost) -> bool:
    try:
        subprocess.check_output(
            "ping -{} 1 {}".format("n" if platform.system().lower() == "windows" else "c", sHost), shell=True
        )
    except Exception:
        return False

    return True

def set_scale(raw, item):
    scale = 0
    try:
        # Domoticz.Debug('Scale :' + str(item['values'].get('scale', 0 )))
        if item['values'] in 'scale':
            scale = item['values'].get('scale')
        # step = the_values.get('step', 0)
        if item['values'] in 'unit':
            unit = item['values'].get('unit')
        if item['values'] in 'max':
            max = item['values'].get('max')

        if scale == 1:
            result = int(raw * 10)
        elif scale == 2:
            result = int(raw * 100)
        elif scale == 3:
            result = int(raw * 1000)
        else:
            result = int(raw)
        if result > max:
            result = int(max)
            Domoticz.Log('Value higher then maximum device')
        elif result < min:
            result = int(min)
            Domoticz.Log('Value lower then minium device')
    except:
        result = str(raw)
    return result

def get_scale(raw, item):
    scale = 0

    # Check if raw is a valid number (int, float, or numeric string)
    if not isinstance(raw, (list, tuple, dict, set, bool, complex, bytes, str)) or (isinstance(raw, str) and raw.isnumeric()):
        # Convert numeric strings to floats
        raw = float(raw) if isinstance(raw, str) else raw

        try:
            # Domoticz.Debug('Raw Value: ' + str(raw) + '  Type: ' + str(type(raw)))
            # Domoticz.Debug('Item Values: ' + str(item['values']))
            if item['values'] in 'scale':
                scale = item['values'].get('scale')
            if item['values'] in 'unit':
                unit = item['values'].get('unit')
            if item['values'] in 'max':
                max_value = item['values'].get('max')

            if scale == 0:
                if unit == 'V' and len(str(max_value)) >= 4:
                    result = raw / 10
                elif unit == 'W' and len(str(max_value)) >= 5:
                    result = raw / 10
                else:
                    result = int(raw)
            elif scale == 1:
                result = raw / 10
            elif scale == 2:
                result = raw / 100
            elif scale == 3:
                result = raw / 1000
            else:
                result = int(raw)
        except:
            result = raw
    else:
        # If raw is not numeric, return it unmodified
        result = raw
        Domoticz.Debug('Non-numeric input, returning raw value: ' + str(result))

    return result

    # Configuration Helpers
def getConfigItem(Key=None, Values=None):
    Value = {}
    try:
        Config = Domoticz.Configuration()
        if (Key != None):
            # Domoticz.Debug(Config[Key][Values])
            Value = Config[Key][Values]  # only return requested key if there was one
        else:
            Value = Config      # return the whole configuration if no key
    except KeyError:
        Value = {}
    except Exception as inst:
        Domoticz.Error('Domoticz.Configuration read failed: ' + str(inst))
    return Value

def setConfigItem(Key=None, Value=None):
    Config = {}
    try:
        Config = Domoticz.Configuration()
        if (Key != None):
            Config[Key] = Value
        else:
            Config = Value  # set whole configuration if no key specified
        Config = Domoticz.Configuration(Config)
    except Exception as inst:
        Domoticz.Error('Domoticz.Configuration operation failed: ' + str(inst))
    return Config

def version(v):
    return tuple(map(int, (v.split("."))))