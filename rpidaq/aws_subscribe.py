# %%
import os
import argparse
import logging
import json
import time
import yaml

from common import aws
from getmac import get_mac_address as gma

# modified from example provided by Gary A. Stafford
# MQTT connection code is modified version of aws-iot-device-sdk-python-v2 sample:
# https://github.com/aws/aws-iot-device-sdk-python-v2/blob/master/samples/pubsub.py


# Read in command-line parameters
def parse_args(cfg):
    parser = argparse.ArgumentParser(description="Send and receive messages through and MQTT connection.")
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
    parser.add_argument('--verbosity', choices=[x.name for x in aws.io.LogLevel], default=aws.io.LogLevel.NoLogs.name,
                        help='Logging level')
    parser.add_argument("--frequency", default=int(cfg["aws"]["frequency"]), action="store", dest="frequency", type=int,
                        help="IoT event message frequency")
    args = parser.parse_args()
    return parser, args

# %%
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
    aws.io.init_logging(getattr(aws.io.LogLevel, args.verbosity), 'stderr')

    # Print MAC address
    msg = f"MAC address of subscribing device: {gma()}"
    logging.info(msg)
    print(msg)


    # spin up resources
    event_loop_group = aws.io.EventLoopGroup(1)
    host_resolver = aws.io.DefaultHostResolver(event_loop_group)
    client_bootstrap = aws.io.ClientBootstrap(event_loop_group, host_resolver)

    # set MQTT connection
    mqtt_connection = aws.set_mqtt_connection(args, client_bootstrap)
    msg = f"Connecting to '{args.endpoint}' with client ID '{args.client_id}' ..."
    logging.info(msg)
    print(msg)

    connect_future = mqtt_connection.connect()

    # Future.result() waits until a result is available
    connect_future.result()
    print(connect_future.result())
    logging.info("Connected!")
    print("Connected!")

    # Subscribe (this will pull in messages from other devices)
    msg = f"Subscribing to topic '{args.topic}' ..."
    logging.info(msg)
    print(msg)
    subscribe_future, packet_id = mqtt_connection.subscribe(
        topic=args.topic,
        qos=aws.mqtt.QoS.AT_LEAST_ONCE,
        callback=aws.on_message_received)
    subscribe_result = subscribe_future.result()
    msg = f"Subscribed with {str(subscribe_result['qos'])}"
    logging.info(msg)
    print(msg)

    # # Wait for all messages to be received.
    # # This waits forever if count was set to 0.
    # if message_count != 0 and not received_all_event.is_set():
    #     print("Waiting for all messages to be received...")

    # received_all_event.wait()
    # print("{} message(s) received.".format(received_count))

    # # Disconnect
    # print("Disconnecting...")
    # disconnect_future = mqtt_connection.disconnect()
    # disconnect_future.result()
    # print("Disconnected!")

# %%
if __name__ == "__main__":
    main()
