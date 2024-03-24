from hilinkapi.HiLinkAPI import webui
import argparse
import datetime
import logging
import requests
import time
import xmltodict


class PushoverAPI:
    def __init__(self, user, token) -> None:
        self.user = user
        self.token = token
    
    def sendNotification(self, title: str, message: str, message_time: datetime.datetime) -> None:
        unix_timestamp = int(time.mktime(message_time.timetuple()))
        resp = requests.post("https://api.pushover.net/1/messages.json", {
            'token': self.token,
            'user': self.user,
            'title': title,
            'message': message,
            'timestamp': unix_timestamp
        })
        if not resp.ok:
            raise Exception("Could not post message to pushover.", resp)


class HuaweiAPI:
    INIT_TIMEOUT_SECONDS = 60

    def __init__(self, name : str, ip : str, user : str, password : str) -> None:
        self.api = webui(name, ip, user, password, logging)
        self.api.start()
        self.initialize()

    def initialize(self):
        # wait until validate the session
        limit = time.time() + HuaweiAPI.INIT_TIMEOUT_SECONDS
        while not self.api.getValidSession():
            # abort if timeout reached
            if time.time() > limit:
                raise Exception("Timeout while initializing API")
            # check for active errors
            if self.api.getActiveError() is not None:
                error = self.api.getActiveError()
                logging.error(error)
                time.sleep(5)
            # check for login wait time
            if self.api.getLoginWaitTime() > 0:
                logging.info(f"Login wait time available = {self.api.getLoginWaitTime()} minutes")
                time.sleep(5)
    
    def deleteSms(self, id : str):
        endpoint = "/api/sms/delete-sms"
        payload = xmltodict.unparse({
            'request': {
                'Index': id
            }
        })
        resp = self._httpPost(endpoint, payload)
        content = xmltodict.parse(resp.text)
        if content['response'] != "OK":
            raise Exception(f"Could not delete sms with index {id}")

    def getFirstSms(self):
        endpoint = "/api/sms/sms-list"
        payload = xmltodict.unparse({
            'request': {
                'PageIndex': '1',
                'ReadCount': '1',
                'BoxType': '1',
                'SortType': '0',
                'Ascending': '0',
                'UnreadPreferred': '1'
            }
        })
        resp = self._httpPost(endpoint, payload)
        content = xmltodict.parse(resp.text)
        xml_response = content['response']
        number_of_messages = int(xml_response['Count'])
        if number_of_messages < 1:
            return None
        return xml_response['Messages']['Message']

    def _httpPost(self, endpoint : str, payload : str) -> requests.Response:
        if not self.api.getValidSession():
            self.initialize()

        headers = {
            'X-Requested-With':'XMLHttpRequest',
            '__RequestVerificationToken': self.api._RequestVerificationToken
        }
        resp = self.api.httpPost(endpoint, payload, None, headers)
        if not resp.ok:
            raise Exception('Error in posting request.')
        return resp


def action(hilink: HuaweiAPI, pushover: PushoverAPI):
    # read next SMS
    logging.info('Polling for new SMS')
    sms = hilink.getFirstSms()
    if sms is None:
        logging.info('No SMS found')
        return
    
    # read attributes of SMS
    sms_index = sms['Index']
    sms_sender = sms['Phone']
    sms_text = sms['Content']
    sms_time = datetime.datetime.strptime(sms['Date'], '%Y-%m-%d %H:%M:%S')
    local_tz = datetime.datetime.now().astimezone().tzinfo
    sms_time.replace(tzinfo=local_tz)
    logging.debug('SMS found: %s', sms)

    # send SMS via pushover
    logging.info('Sending SMS via pushover')
    pushover.sendNotification(
        title=f"SMS from {sms_sender}",
        message=sms_text,
        message_time=sms_time
    )

    # delete SMS
    logging.info('Deleting SMS')
    hilink.deleteSms(sms_index)


def start_loop(hilink_modem_name:str, hilink_api: str, hilink_user: str, hilink_password: str, pushover_user: str, pushover_token: str):
    hilink = HuaweiAPI(hilink_modem_name, hilink_api, hilink_user, hilink_password)
    pushover = PushoverAPI(pushover_user, pushover_token)

    while True:
        action(hilink, pushover)
        time.sleep(10)


def cli():
    # parse configuration from command line
    parser = argparse.ArgumentParser(
        prog='Hilink2Pushover',
        description='Periodically polls sms and sends them to pushover',
        fromfile_prefix_chars='@'
    )
    parser.add_argument('--hilink-modem-name', default='MODEM')
    parser.add_argument('--hilink-ip', default='192.168.8.1')
    parser.add_argument('--hilink-user', default='admin')
    parser.add_argument('--hilink-password', required=True)
    parser.add_argument('--pushover-user', required=True)
    parser.add_argument('--pushover-token', required=True)
    parser.add_argument('--log-level', choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'], default='INFO')
    args = parser.parse_args()

    # configure logging
    logging.basicConfig(format='%(asctime)s --  %(name)s::%(levelname)s -- {%(pathname)s:%(lineno)d} -- %(message)s', level=args.log_level, datefmt="%Y-%m-%d %I:%M:%S %p:%Z")

    # start processing loop
    start_loop(args.hilink_modem_name, args.hilink_ip, args.hilink_user, args.hilink_password, args.pushover_user, args.pushover_token)


if __name__ == '__main__':
    cli()
