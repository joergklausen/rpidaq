# import logging
import os
import threading
import time
import json
import yaml
from awscrt import io, mqtt
from awsiot import mqtt_connection_builder
# from getmac import get_mac_address as gma
from sps30.sps30 import SPS30
from scd30.scd30 import SCD30

# Shadow JSON schema:
#
# {
#   "state": {
#       "desired":{
#           "RH":<INT VALUE>,
#           "T":<INT VALUE>            
#       }
#   }
# }

# Function called when a shadow is updated
# def customShadowCallback_Update(payload, responseStatus, token):
# 
#     # Display status and data from update request
#     if responseStatus == "timeout":
#         print("Update request " + token + " time out!")
# 
#     if responseStatus == "accepted":
#         payloadDict = json.loads(payload)
#         print("~~~~~~~~~~~~~~~~~~~~~~~")
#         print("Update request with token: " + token + " accepted!")
#         print("RH: " + str(payloadDict["state"]["reported"]["RH"]))
#         print("Terature: " + str(payloadDict["state"]["reported"]["T"]))
#         print("~~~~~~~~~~~~~~~~~~~~~~~\n\n")
# 
#     if responseStatus == "rejected":
#         print("Update request " + token + " rejected!")
# 
# # Function called when a shadow is deleted
# def customShadowCallback_Delete(payload, responseStatus, token):
# 
#      # Display status and data from delete request
#     if responseStatus == "timeout":
#         print("Delete request " + token + " time out!")
# 
#     if responseStatus == "accepted":
#         print("~~~~~~~~~~~~~~~~~~~~~~~")
#         print("Delete request with token: " + token + " accepted!")
#         print("~~~~~~~~~~~~~~~~~~~~~~~\n\n")
# 
#     if responseStatus == "rejected":
#         print("Delete request " + token + " rejected!")


# Read in command-line parameters
# def parseArgs():
# 
#     parser = argparse.ArgumentParser()
#     parser.add_argument("-e", "--endpoint", action="store", required=True, dest="host", help="Your device data endpoint")
#     parser.add_argument("-r", "--rootCA", action="store", required=True, dest="rootCAPath", help="Root CA file path")
#     parser.add_argument("-c", "--cert", action="store", dest="certificatePath", help="Certificate file path")
#     parser.add_argument("-k", "--key", action="store", dest="privateKeyPath", help="Private key file path")
#     parser.add_argument("-p", "--port", action="store", dest="port", type=int, help="Port number override")
#     parser.add_argument("-n", "--thingName", action="store", dest="thingName", default="Bot", help="Targeted thing name")
#     parser.add_argument("-id", "--clientId", action="store", dest="clientId", default="basicShadowUpdater", help="Targeted client id")
# 
#     args = parser.parse_args()
#     return args

# Callback when connection is accidentally lost.
def on_connection_interrupted(connection, error, **kwargs):
    print("Connection interrupted. error: {}".format(error))


# Callback when an interrupted connection is re-established.
def on_connection_resumed(connection, return_code, session_present, **kwargs):
    print("Connection resumed. return_code: {} session_present: {}".format(return_code, session_present))

    if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
        print("Session did not persist. Resubscribing to existing topics...")
        resubscribe_future, _ = connection.resubscribe_existing_topics()

        # Cannot synchronously wait for resubscribe result because we're on the connection's event-loop thread,
        # evaluate result with a callback instead.
        resubscribe_future.add_done_callback(on_resubscribe_complete)


def on_resubscribe_complete(resubscribe_future):
    resubscribe_results = resubscribe_future.result()
    print("Resubscribe results: {}".format(resubscribe_results))

    for topic, qos in resubscribe_results['topics']:
        if qos is None:
            sys.exit("Server rejected resubscribe to topic: {}".format(topic))

# Callback when the subscribed topic receives a message
def on_message_received(topic, payload, **kwargs):
    print(f"Received message from topic '{topic}': {payload}")
    global received_count
    received_count += 1
    if received_count == count:
        received_all_event.set()


# def set_mqtt_connection(args, client_bootstrap):
#     if args.use_websocket:
#         proxy_options = None
#         if args.proxy_host:
#             proxy_options = http.HttpProxyOptions(host_name=args.proxy_host, port=args.proxy_port)
# 
#         credentials_provider = auth.AwsCredentialsProvider.new_default_chain(client_bootstrap)
#         mqtt_connection = mqtt_connection_builder.websockets_with_default_aws_signing(
#             endpoint=args.endpoint,
#             client_bootstrap=client_bootstrap,
#             region=args.signing_region,
#             credentials_provider=credentials_provider,
#             websocket_proxy_options=proxy_options,
#             ca_filepath=args.root_ca,
#             on_connection_interrupted=on_connection_interrupted,
#             on_connection_resumed=on_connection_resumed,
#             client_id=args.client_id,
#             clean_session=False,
#             keep_alive_secs=6)
# 
#     else:
#         mqtt_connection = mqtt_connection_builder.mtls_from_path(
#             endpoint=args.endpoint,
#             cert_filepath=args.cert,
#             pri_key_filepath=args.key,
#             client_bootstrap=client_bootstrap,
#             ca_filepath=args.root_ca,
#             on_connection_interrupted=on_connection_interrupted,
#             on_connection_resumed=on_connection_resumed,
#             client_id=args.client_id,
#             clean_session=False,
#             keep_alive_secs=6)
# 
#     return mqtt_connection

# Global Variables
count: int = 0  # from args
# received_count: int = 0
received_all_event = threading.Event()


# %%
if __name__ == "__main__":

    # read config file
    with open("app.cfg", "r") as f:
        cfg = yaml.safe_load(f)
        f.close()
    cfg["aws"]["key"] = os.path.expanduser(cfg["aws"]["key"])
    cfg["aws"]["cert"] = os.path.expanduser(cfg["aws"]["cert"])
    cfg["aws"]["root_ca"] = os.path.expanduser(cfg["aws"]["root_ca"])
    
    # initialize sensors
    pm_sensor = None
    if cfg["sensors"]["sps30"]:
        pm_sensor = SPS30()
        pm_sensor_cfg = {
            "Product type": pm_sensor.get_product_type(), 
            "Serial number": pm_sensor.get_serial_number(),
            "Firmware version": pm_sensor.get_firmware_version(),
            "Status register": pm_sensor.get_status_register(),
            "Auto cleaning interval": pm_sensor.get_auto_cleaning_interval()
            }
        print(pm_sensor_cfg)
        with open(os.path.expanduser(cfg['data']) + "/sps30.json", "wt") as fh:
            fh.write(json.dumps(pm_sensor_cfg))
            fh.write("\n")
        pm_sensor.start_measurement()
        time.sleep(5)

    co2_sensor = None    
    if cfg["sensors"]["scd30"]:
        co2_sensor = SCD30(sampling_period=60)
        co2_sensor_cfg = {
            "Product type": "SCD30",
            "Firmware version": co2_sensor.get_firmware_version()
            }
        print(co2_sensor_cfg)
        with open(os.path.expanduser(cfg['data']) + "/scd30.json", "wt") as fh:
            fh.write(json.dumps(co2_sensor_cfg))
            fh.write("\n")
        co2_sensor.start_measurement()
        time.sleep(5)

    # set log level
#     io.init_logging(getattr(io.LogLevel, str(cfg['verbosity'])), 'stderr')

    # spin up resources
    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)
    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=cfg["aws"]["endpoint"],
        cert_filepath=cfg["aws"]["cert"],
        pri_key_filepath=cfg["aws"]["key"],
        client_bootstrap=client_bootstrap,
        ca_filepath=cfg["aws"]["root_ca"],
        on_connection_interrupted=on_connection_interrupted,
        on_connection_resumed=on_connection_resumed,
        client_id=cfg["aws"]["client_id"],
        clean_session=False,
        keep_alive_secs=6)

    print(f"Connecting to {cfg['aws']['endpoint']} with client ID: {cfg['aws']['client_id']} ...")

    # connect
    connect_future = mqtt_connection.connect()

    # Future.result() waits until a result is available
    connect_future.result()
    print("Connection to AWS IoT Core established.")

    # Subscribe (this will pull in messages down from other devices)
    print(f"Subscribing to topic '{cfg['aws']['topic']}'...")
    subscribe_future, packet_id = mqtt_connection.subscribe(
        topic=cfg["aws"]["topic"],
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_message_received)
    
    subscribe_result = subscribe_future.result()
    print(f"Subscribed with {str(subscribe_result['qos'])}")

    # begin publication
    publish = True
    count = 0
    counts = cfg["aws"]["counts"]
    print("Begin publication of results.")
    while publish:
        count += 1
        if counts == 0:
            # loop until interrupted
            publish = True
        elif count > counts:
            publish = False
            print("Stop publication of results.")
            disconnect_future = mqtt_connection.disconnect()
            disconnect_future.result()
            print("Connection disconnected - Goodbye!")
            break
            
        # Create message payload
        pm_sensor_result = pm_sensor.get_measurement()
        c02_sensor_result = co2_sensor.get_measurement()

        payload = {
#             "device_id": gma(),
            "ts": time.time(),
            "data": {
                "dtm_pm_sensor": pm_sensor_result['timestamp'],
                "mass_density_pm1.0": pm_sensor_result['mass_density']['pm1.0'],
                "mass_density_pm2.5": pm_sensor_result['mass_density']['pm2.5'],
                "mass_density_pm4.0": pm_sensor_result['mass_density']['pm4.0'],
                "mass_density_pm10": pm_sensor_result['mass_density']['pm10'],
                "particle_count_pm0.5": pm_sensor_result['particle_count']['pm0.5'],
                "particle_count_pm1.0":pm_sensor_result['particle_count']['pm1.0'],
                "particle_count_pm2.5":pm_sensor_result['particle_count']['pm2.5'],
                "particle_count_pm4.0":pm_sensor_result['particle_count']['pm4.0'],
                "particle_count_pm10":pm_sensor_result['particle_count']['pm10'],
                "dtm_c02_sensor": c02_sensor_result['timestamp'],
                "CO2": c02_sensor_result['CO2'],
                "T": c02_sensor_result['T'],
                "RH": c02_sensor_result['RH']
            }
        }
        
        # Don't send bad messages!
        if payload["data"]["dtm_pm_sensor"] is not None \
                and payload["data"]["dtm_c02_sensor"] is not None:
            # Publish Message
            message_json = json.dumps(payload, sort_keys=True, indent=None, separators=(',', ':'))

            try:
                mqtt_connection.publish(
                    topic=cfg["aws"]["topic"],
                    payload=message_json,
                    qos=mqtt.QoS.AT_LEAST_ONCE)
                print(f"Message {count}/{counts} published to topic: {cfg['aws']['topic']}.")
                time.sleep(cfg["aws"]["frequency"])
#             except mqtt.SubscribeError as err:
#                 print(".SubscribeError: {}".format(err))
#             except exceptions.AwsCrtError as err:
#                 print("AwsCrtError: {}".format(err))
            except Exception as err:
                print(err)
                
        else:
            print("Sensor failure ... retrying ...")
