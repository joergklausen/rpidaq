import json
import logging
import sys
import threading
import time
from awscrt import io, mqtt, auth, http, exceptions
from awsiot import mqtt_connection_builder

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

# Callback when connection is accidentally lost.
def on_connection_interrupted(connection, error, **kwargs):
    logging.error(f"Connection interrupted. error: {error}")


# Callback when an interrupted connection is re-established.
def on_connection_resumed(connection, return_code, session_present, **kwargs):
    logging.info(f"Connection resumed. return_code: {return_code} session_present: {session_present}")

    if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
        logging.warning(f"Session did not persist. Resubscribing to existing topics...")
        resubscribe_future, _ = connection.resubscribe_existing_topics()

        # Cannot synchronously wait for resubscribe result because we're on the connection's event-loop thread,
        # evaluate result with a callback instead.
        resubscribe_future.add_done_callback(on_resubscribe_complete)


def on_resubscribe_complete(resubscribe_future):
    resubscribe_results = resubscribe_future.result()
    logging.info(f"Resubscribe results: {resubscribe_results}")

    for topic, qos in resubscribe_results['topics']:
        if qos is None:
            logging.warning(f"Server rejected resubscribe to topic: {topic}")


# Callback when the subscribed topic receives a message
def on_message_received(topic, payload, **kwargs):
    logging.info(f"Received message from topic '{topic}': {payload}")
    global received_count
    received_count += 1
    if received_count == count:
        received_all_event.set()

def publish_message(mqtt_connection, args, payload:str):
    message_json = json.dumps(payload, sort_keys=False, indent=None, separators=(',', ':'))

    try:
        mqtt_connection.publish(
            topic=args.topic,
            payload=message_json,
            qos=mqtt.QoS.AT_LEAST_ONCE)
        logging.info(f"Message {message_json} published.")

    except mqtt.SubscribeError as err:
        logging.error(f".SubscribeError: {err}")
    except exceptions.AwsCrtError as err:
        logging.error(f"AwsCrtError: {err}")
    else:
        time.sleep(args.frequency)
