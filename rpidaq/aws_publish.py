import os
import argparse
import json
import sys
import threading
import time
import random
import yaml

# import adafruit_dht
from awscrt import io, mqtt, auth, http, exceptions
from awsiot import mqtt_connection_builder
from getmac import get_mac_address as gma
from sps30.sps30 import SPS30
from scd30.scd30 import SCD30

# modified from example provided by Gary A. Stafford
# MQTT connection code is modified version of aws-iot-device-sdk-python-v2 sample:
# https://github.com/aws/aws-iot-device-sdk-python-v2/blob/master/samples/pubsub.py

# Global Variables
count: int = 0  # from args
received_count: int = 0
received_all_event = threading.Event()


def set_mqtt_connection(args, client_bootstrap):
    if args.use_websocket:
        proxy_options = None
        if args.proxy_host:
            proxy_options = http.HttpProxyOptions(host_name=args.proxy_host, port=args.proxy_port)

        credentials_provider = auth.AwsCredentialsProvider.new_default_chain(client_bootstrap)
        mqtt_connection = mqtt_connection_builder.websockets_with_default_aws_signing(
            endpoint=args.endpoint,
            client_bootstrap=client_bootstrap,
            region=args.signing_region,
            credentials_provider=credentials_provider,
            websocket_proxy_options=proxy_options,
            ca_filepath=args.root_ca,
            on_connection_interrupted=on_connection_interrupted,
            on_connection_resumed=on_connection_resumed,
            client_id=args.client_id,
            clean_session=False,
            keep_alive_secs=6)

    else:
        mqtt_connection = mqtt_connection_builder.mtls_from_path(
            endpoint=args.endpoint,
            cert_filepath=args.cert,
            pri_key_filepath=args.key,
            client_bootstrap=client_bootstrap,
            ca_filepath=args.root_ca,
            on_connection_interrupted=on_connection_interrupted,
            on_connection_resumed=on_connection_resumed,
            client_id=args.client_id,
            clean_session=False,
            keep_alive_secs=6)

    return mqtt_connection

def get_rndnum():
    return {"rndnum": random.random() }


# Read in command-line parameters
def parse_args(cfg):
    parser = argparse.ArgumentParser(description="Send and receive messages through and MQTT connection.")
#    parser.add_argument('--endpoint', required=True, help="Your AWS IoT custom endpoint, not including a port. " +
#                                                           "Ex: \"abcd123456wxyz-ats.iot.us-east-1.amazonaws.com\"")
    parser.add_argument('--endpoint', default=cfg["aws"]["endpoint"], help="Your AWS IoT custom endpoint, not including a port. " +
                                                          "Ex: \"abcd123456wxyz-ats.iot.us-east-1.amazonaws.com\"")
    parser.add_argument('--cert', default=cfg["aws"]["cert"], help="File path to your client certificate, in PEM format.")
    parser.add_argument('--key', default=cfg["aws"]["key"], help="File path to your private key, in PEM format.")
    parser.add_argument('--root-ca', default=cfg["aws"]["root_ca"], help="File path to root certificate authority, in PEM format. " +
                                          "Necessary if MQTT server uses a certificate that's not already in " +
                                          "your trust store.")
    parser.add_argument('--client-id', default=cfg["aws"]["client_id"], help="Client ID for MQTT connection.")
    parser.add_argument('--topic', default=cfg["aws"]["topic"], help="Topic to subscribe to, and publish messages to.")
    parser.add_argument('--message', default="Hello World!", help="Message to publish. " +
                                                                  "Specify empty string to publish nothing.")
    parser.add_argument('--count', default=0, type=int, help="Number of messages to publish/receive before exiting. " +
                                                             "Specify 0 to run forever.")
    parser.add_argument('--use-websocket', default=False, action='store_true',
                        help="To use a websocket instead of raw mqtt. If you specify this option you must "
                             "specify a region for signing, you can also enable proxy mode.")
    parser.add_argument('--signing-region', default='us-east-1',
                        help="If you specify --use-web-socket, this is the region that will be used for computing "
                             "the Sigv4 signature")
    parser.add_argument('--proxy-host', help="Hostname for proxy to connect to. Note: if you use this feature, " +
                                             "you will likely need to set --root-ca to the ca for your proxy.")
    parser.add_argument('--proxy-port', type=int, default=8080, help="Port for proxy to connect to.")
    parser.add_argument('--verbosity', choices=[x.name for x in io.LogLevel], default=io.LogLevel.NoLogs.name,
                        help='Logging level')
    parser.add_argument("--frequency", default=cfg["aws"]["frequency"], action="store", dest="frequency", type=int,
                        help="IoT event message frequency")

    args = parser.parse_args()
    return parser, args


# Callback when connection is accidentally lost.
def on_connection_interrupted(connection, error, **kwargs):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} Connection interrupted. error: {error}")


# Callback when an interrupted connection is re-established.
def on_connection_resumed(connection, return_code, session_present, **kwargs):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} Connection resumed. return_code: {return_code} session_present: {session_present}")

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
    print("Received message from topic '{}': {}".format(topic, payload))
    global received_count
    received_count += 1
    if received_count == count:
        received_all_event.set()


def main():
    # read config file
    with open("app.cfg", "r") as f:
        cfg = yaml.safe_load(f)
        f.close()
    cfg["aws"]["key"] = os.path.expanduser(cfg["aws"]["key"])
    cfg["aws"]["cert"] = os.path.expanduser(cfg["aws"]["cert"])
    cfg["aws"]["root_ca"] = os.path.expanduser(cfg["aws"]["root_ca"])

    # parse command line arguments (over-writes config)
    parser, args = parse_args(cfg)
       
    global count
    count = args.count

    # set log level
    io.init_logging(getattr(io.LogLevel, args.verbosity), 'stderr')

    # Print MAC address
    print(gma())

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
        time.sleep(1)

    co2_sensor = None    
    if cfg["sensors"]["scd30"]:
        co2_sensor = SCD30(sampling_period=cfg["scd30"]["sampling_period"], pressure=cfg["scd30"]["pressure"])
        co2_sensor_cfg = {
            "Product type": "SCD30",
            "Firmware version": co2_sensor.get_firmware_version()
            }
        print(co2_sensor_cfg)
        with open(os.path.expanduser(cfg['data']) + "/scd30.json", "wt") as fh:
            fh.write(json.dumps(co2_sensor_cfg))
            fh.write("\n")
        co2_sensor.start_measurement()
        time.sleep(1)

    # spin up resources
    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

    # set MQTT connection
    mqtt_connection = set_mqtt_connection(args, client_bootstrap)

    print(f"Connecting to '{args.endpoint}' with client ID '{args.client_id}'...")

    connect_future = mqtt_connection.connect()

    # Future.result() waits until a result is available
    connect_future.result()
    print(connect_future.result())
    print("Connected!")

    # Subscribe (this will pull in messages down from other devices)
#     print("Subscribing to topic '{}'...".format(args.topic))
#     subscribe_future, packet_id = mqtt_connection.subscribe(
#         topic=args.topic,
#         qos=mqtt.QoS.AT_LEAST_ONCE,
#         callback=on_message_received)
#     subscribe_result = subscribe_future.result()
#     print("Subscribed with {}".format(str(subscribe_result['qos'])))

    while True:
        # Create message payload
        pm_sensor_result = pm_sensor.get_measurement()
        co2_sensor_result = co2_sensor.get_measurement()
#         print(f"scd30 returned: {co2_sensor_result}")
#         payload_rndnum = get_rndnum()
#         print(payload_rndnum)

        payload = {
            "device_id": gma(),
            "ts": time.time(),
            "data": {
#                 "rndnum": payload_rndnum["rndnum"],
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
                "dtm_co2_sensor": co2_sensor_result['timestamp'],
                "CO2": co2_sensor_result['CO2'],
                "T": co2_sensor_result['T'],
                "RH": co2_sensor_result['RH']
            }
        }

        # persist data in file
        dte = time.strftime("%Y%m%d", time.gmtime())
        if pm_sensor:
            with open(f"{os.path.expanduser(cfg['data'])}/sps30-{dte}.json", "at") as fh:
                fh.write(f"{pm_sensor_result['timestamp']}")
                fh.write(f",{pm_sensor_result['mass_density']['pm1.0']}")
                fh.write(f",{pm_sensor_result['mass_density']['pm2.5']}")
                fh.write(f",{pm_sensor_result['mass_density']['pm4.0']}")
                fh.write(f",{pm_sensor_result['mass_density']['pm10']}")
                fh.write(f",{pm_sensor_result['particle_count']['pm0.5']}")
                fh.write(f",{pm_sensor_result['particle_count']['pm1.0']}")
                fh.write(f",{pm_sensor_result['particle_count']['pm2.5']}")
                fh.write(f",{pm_sensor_result['particle_count']['pm4.0']}")
                fh.write(f",{pm_sensor_result['particle_count']['pm10']}\n")
        if co2_sensor:
            with open(f"{os.path.expanduser(cfg['data'])}/scd30-{dte}.json", "at") as fh:
                fh.write(f"{co2_sensor_result['timestamp']}")
                fh.write(f",{co2_sensor_result['CO2']}")
                fh.write(f",{co2_sensor_result['T']}")
                fh.write(f",{co2_sensor_result['RH']}\n")

        # Don't send bad messages!
#         if payload["data"]["temp"] is not None \
#                 and payload["data"]["humidity"] is not None \
#                 and payload["data"]["co"] is not None:
        if payload["data"]["dtm_pm_sensor"] is not None:            # Publish Message
            message_json = json.dumps(payload, sort_keys=True, indent=None, separators=(',', ':'))

            try:
                mqtt_connection.publish(
                    topic=args.topic,
                    payload=message_json,
                    qos=mqtt.QoS.AT_LEAST_ONCE)
                print(f"message {message_json} published.")
            except mqtt.SubscribeError as err:
                print(".SubscribeError: {}".format(err))
            except exceptions.AwsCrtError as err:
                print("AwsCrtError: {}".format(err))
            else:
                time.sleep(args.frequency)
        else:
            print("sensor failure...retrying...")


if __name__ == "__main__":
    main()
#     sys.exit(main())